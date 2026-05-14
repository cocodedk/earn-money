"""Tests for triage.draft_llm.polish_draft()."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from earn_money import config, db
from earn_money.agent.structured import StructuredOutputError
from earn_money.triage import draft_llm
from tests.triage.conftest import make_finding, register_program

_SKELETON = (
    "---\nfinding_hash: h1\nplatform: hackerone\n---\n"
    "# CVE-2023-1234\n\n"
    "## Summary\n\n[summary placeholder]\n\n"
    "## Affected asset\n\n- URL: https://api.example.com/\n\n"
    "## Steps to Reproduce\n\n[steps placeholder]\n\n"
    "## Impact\n\n[impact placeholder]\n\n"
    "## Proof of concept\n\n[poc]\n"
)
_LLM_RESULT = {
    "summary": "SQL injection in search endpoint.",
    "steps": "1. Visit https://api.example.com/search?q='\n2. Observe error.",
    "impact": "Attacker can read arbitrary database rows.",
}


def _p(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _skeleton(paths: config.Paths) -> Path:
    d = paths.root / "reports" / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "h1.md"
    p.write_text(_SKELETON, encoding="utf-8")
    return p


def _seed(paths: config.Paths, evidence_rel: str = "recon/outputs/r1/raw.jsonl") -> None:
    register_program(paths)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    from earn_money.triage import findings, history

    findings.upsert_finding(conn, make_finding(evidence_path=evidence_rel))
    history.transition_state(
        conn,
        finding_hash="h1",
        to_state="verified",
        actor="operator",
        note=None,
        now="2026-05-15T10:00:00Z",
    )
    conn.commit()
    conn.close()


def test_polish_splices_sections(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths)
    _skeleton(paths)

    with patch("earn_money.triage.draft_llm.request_structured", return_value=_LLM_RESULT):
        result = draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )

    text = result.read_text(encoding="utf-8")
    assert "SQL injection in search endpoint." in text
    assert "1. Visit https://api.example.com/search" in text
    assert "Attacker can read arbitrary database rows." in text
    assert "[summary placeholder]" not in text
    assert "[steps placeholder]" not in text
    assert "[impact placeholder]" not in text


def test_polish_raises_draft_not_found(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths)
    with pytest.raises(draft_llm.DraftNotFound):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )


def test_polish_raises_on_missing_header(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths)
    d = paths.root / "reports" / "drafts"
    d.mkdir(parents=True)
    (d / "h1.md").write_text(
        "# T\n\n## Summary\n\n[s]\n\n## Impact\n\n[i]\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="missing section"):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )


def test_polish_passes_evidence_to_llm(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    ev = paths.root / "recon" / "outputs" / "r1" / "raw.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text('{"hit": "xss"}', encoding="utf-8")
    _seed(paths, evidence_rel="recon/outputs/r1/raw.jsonl")
    _skeleton(paths)

    captured: dict = {}

    def fake(provider, *, system, user, schema, task, validator):
        captured["user"] = user
        return _LLM_RESULT

    with patch("earn_money.triage.draft_llm.request_structured", fake):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )

    assert "---EVIDENCE---" in captured["user"]
    assert '{"hit": "xss"}' in captured["user"]


def test_polish_truncates_evidence(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    ev = paths.root / "recon" / "outputs" / "r1" / "raw.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_bytes(b"x" * 20_000)
    _seed(paths, evidence_rel="recon/outputs/r1/raw.jsonl")
    _skeleton(paths)

    captured: dict = {}

    def fake(provider, *, system, user, schema, task, validator):
        captured["user"] = user
        return _LLM_RESULT

    with patch("earn_money.triage.draft_llm.request_structured", fake):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )

    ev_section = captured["user"].split("---EVIDENCE---")[1]
    assert len(ev_section.encode()) <= 8200


def test_polish_missing_evidence_file_no_crash(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths, evidence_rel="recon/outputs/nonexistent.jsonl")
    _skeleton(paths)

    with patch("earn_money.triage.draft_llm.request_structured", return_value=_LLM_RESULT):
        result = draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )

    assert result.exists()


def test_polish_rejects_path_traversal(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths, evidence_rel="../../../etc/passwd")
    _skeleton(paths)

    with pytest.raises(ValueError, match="escapes repo root"):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )


def test_polish_propagates_structured_output_error(tmp_path: Path) -> None:
    paths = _p(tmp_path)
    _seed(paths)
    _skeleton(paths)

    with patch(
        "earn_money.triage.draft_llm.request_structured",
        side_effect=StructuredOutputError("bad"),
    ), pytest.raises(StructuredOutputError):
        draft_llm.polish_draft(
            paths,
            platform="hackerone",
            slug="example",
            finding_hash="h1",
            provider=object(),
        )


def test_validate_rejects_empty_string() -> None:
    from earn_money.triage.draft_llm import _validate

    with pytest.raises(ValueError, match="non-empty"):
        _validate({"summary": "", "steps": "ok", "impact": "ok"})


def test_validate_rejects_header_at_start() -> None:
    from earn_money.triage.draft_llm import _validate

    with pytest.raises(ValueError, match="section header"):
        _validate({"summary": "## New Section\ntext", "steps": "ok", "impact": "ok"})


def test_validate_rejects_inline_header() -> None:
    from earn_money.triage.draft_llm import _validate

    with pytest.raises(ValueError, match="section header"):
        _validate({"summary": "text\n## Injected", "steps": "ok", "impact": "ok"})
