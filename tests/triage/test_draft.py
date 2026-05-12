"""Tests for earn_money.triage.draft — TDD first-pass (RED before GREEN)."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import draft, findings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _seed_verified(conn, finding_hash: str = "abc123") -> findings.Finding:
    """Insert a queued finding, then promote it to verified via raw SQL."""
    f = findings.Finding(
        finding_hash=finding_hash,
        platform="hackerone",
        slug="example",
        vuln_class="sqli",
        asset="api.example.com",
        target="https://api.example.com/search?q=1",
        signature="sqli|reflect|param=q",
        title="SQL injection on /search",
        severity_hint="high",
        confidence=85,
        source_tool="nuclei",
        source_run_id="run-001",
        evidence_path="recon/outputs/hackerone/example/nuclei/raw.jsonl",
        notes_path="findings/_queue/abc123.md",
        first_seen="2026-05-12T08:00:00Z",
        last_seen="2026-05-12T08:00:00Z",
        occurrence_count=1,
        current_state="queued",
        state_changed_at="2026-05-12T08:00:00Z",
        external_report_id=None,
        payout_amount=None,
        payout_currency=None,
    )
    findings.upsert_finding(conn, f)
    conn.execute(
        "UPDATE findings SET current_state='verified', "
        "state_changed_at='2026-05-12T09:00:00Z' WHERE finding_hash=?",
        (finding_hash,),
    )
    conn.commit()
    return findings.find_by_hash(conn, finding_hash)  # type: ignore[return-value]


def _make_template(paths: config.Paths) -> Path:
    tpl_dir = paths.root / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl = tpl_dir / "report-draft.md"
    tpl.write_text(
        "---\nfinding_hash: {{finding_hash}}\nplatform: {{platform}}\n---\n"
        "# {{title}}\nasset: {{asset}}\ntarget: {{target}}\n"
        "tool: {{source_tool}}\nrun: {{source_run_id}}\n"
        "seen: {{first_seen}}\nsig: {{signature}}\nevidence: {{evidence_path}}\n"
        "slug: {{slug}}\nvuln_class: {{vuln_class}}\n"
        "severity_hint: {{severity_hint}}\n{{unknown_key}}\n",
        encoding="utf-8",
    )
    return tpl


def _open_db(paths: config.Paths, platform: str, slug: str):
    return db.open_db(paths.program_db(platform, slug))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_happy_path_writes_draft(tmp_path: Path) -> None:
    """render + draft_for writes reports/drafts/<hash>.md."""
    paths = _paths(tmp_path)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    _seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")

    assert out == paths.root / "reports" / "drafts" / "abc123.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "abc123" in text
    assert "SQL injection on /search" in text


def test_missing_template_raises(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    # do NOT create template
    conn = _open_db(paths, "hackerone", "example")
    _seed_verified(conn)
    conn.close()

    with pytest.raises(draft.TemplateNotFound):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")


def test_refuse_overwrite_existing_draft(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    _seed_verified(conn)
    conn.close()

    # First call succeeds
    draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")

    # Second call must raise
    with pytest.raises(draft.DraftAlreadyExists):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")


def test_missing_finding_raises_value_error(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _make_template(paths)
    # DB exists but no finding with this hash
    _open_db(paths, "hackerone", "example").close()

    with pytest.raises(ValueError, match="not in hackerone/example DB"):
        draft.draft_for(
            paths, platform="hackerone", slug="example", finding_hash="nonexistent"
        )


def test_all_known_placeholders_substituted(tmp_path: Path) -> None:
    """Every {{field}} in the template is replaced; no residual {{known}} tokens."""
    paths = _paths(tmp_path)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    _seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")
    text = out.read_text(encoding="utf-8")

    known_keys = [
        "finding_hash", "platform", "slug", "vuln_class", "asset", "target",
        "signature", "title", "severity_hint", "source_tool", "source_run_id",
        "evidence_path", "first_seen",
    ]
    for key in known_keys:
        assert f"{{{{{key}}}}}" not in text, f"placeholder {{{{{key}}}}} was not substituted"


def test_unknown_placeholder_preserved(tmp_path: Path) -> None:
    """{{unknown_key}} — not a Finding field — passes through unchanged."""
    paths = _paths(tmp_path)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    _seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="abc123")
    text = out.read_text(encoding="utf-8")

    assert "{{unknown_key}}" in text


def test_render_substitutes_fields() -> None:
    """Unit-test render() in isolation, without filesystem or DB."""
    template = "hash={{finding_hash}} title={{title}} unknown={{nope}}"
    f = findings.Finding(
        finding_hash="h1", platform="p", slug="s", vuln_class="v",
        asset="a", target="t", signature="sig", title="MyTitle",
        severity_hint="high", confidence=80,
        source_tool="tool", source_run_id="rid",
        evidence_path="ep", notes_path="np",
        first_seen="ts", last_seen="ts", occurrence_count=1,
        current_state="verified", state_changed_at="ts",
        external_report_id=None, payout_amount=None, payout_currency=None,
    )
    result = draft.render(template, f)
    assert result == "hash=h1 title=MyTitle unknown={{nope}}"
