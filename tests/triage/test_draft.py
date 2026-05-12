"""Tests for earn_money.triage.draft — TDD first-pass (RED before GREEN)."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import draft, findings
from tests.triage.conftest import make_finding, register_program, seed_verified

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


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
    """substitute_template + draft_for writes reports/drafts/<hash>.md."""
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")

    assert out == paths.root / "reports" / "drafts" / "h1.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "h1" in text
    assert "CVE-2023-1234 hit on api.example.com" in text


def test_missing_template_raises(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    # do NOT create template
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    with pytest.raises(draft.TemplateNotFound):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")


def test_refuse_overwrite_existing_draft(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    # First call succeeds
    draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")

    # Second call must raise
    with pytest.raises(draft.DraftAlreadyExists):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")


def test_missing_finding_raises_value_error(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
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
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")
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
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    out = draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")
    text = out.read_text(encoding="utf-8")

    assert "{{unknown_key}}" in text


def test_draft_refuses_non_verified_finding(tmp_path: Path) -> None:
    """draft_for raises ValueError when the finding is not yet verified."""
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    # Insert queued only — do not promote
    findings.upsert_finding(conn, make_finding())
    conn.close()

    with pytest.raises(ValueError, match="not 'verified'"):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")


def test_draft_force_allows_non_verified(tmp_path: Path) -> None:
    """draft_for(force=True) succeeds even for non-verified findings."""
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    findings.upsert_finding(conn, make_finding())
    conn.close()

    out = draft.draft_for(
        paths, platform="hackerone", slug="example", finding_hash="h1", force=True
    )
    assert out.exists()


def test_draft_refuses_unregistered_program(tmp_path: Path) -> None:
    """draft_for raises ValueError and does NOT create the program directory."""
    paths = _paths(tmp_path)
    _make_template(paths)
    # No scope.md — program not registered

    with pytest.raises(ValueError, match="is not registered"):
        draft.draft_for(
            paths, platform="hackerone", slug="typo-program", finding_hash="h1"
        )

    # Phantom directory must NOT have been created
    assert not (paths.root / "programs" / "hackerone" / "typo-program").exists()


def test_unverified_path_does_not_create_drafts_dir(tmp_path: Path) -> None:
    """draft_for must not create reports/drafts/ when the state guard rejects."""
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open_db(paths, "hackerone", "example")
    findings.upsert_finding(conn, make_finding())  # queued only
    conn.close()

    with pytest.raises(ValueError, match="not 'verified'"):
        draft.draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")

    assert not (paths.root / "reports" / "drafts").exists()
