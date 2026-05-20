"""Tests for draft CLI --regenerate flag."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from earn_money import config, db
from earn_money.agent.providers import ProviderUnavailable
from earn_money.agent.structured import StructuredOutputError
from earn_money.triage import draft as draft_mod
from earn_money.triage.draft_llm import DraftNotFound
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


def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _seed(paths: config.Paths) -> None:
    register_program(paths)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    from earn_money.triage import findings, history

    findings.upsert_finding(conn, make_finding())
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


def _skeleton(paths: config.Paths) -> Path:
    d = paths.root / "reports" / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "h1.md"
    p.write_text(_SKELETON, encoding="utf-8")
    return p


def test_regenerate_exits_zero(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    _skeleton(paths)

    with (
        patch("earn_money.triage.draft.from_env", return_value=object()),
        patch("earn_money.triage.draft.polish_draft", return_value=tmp_path / "h1.md"),
    ):
        rc = draft_mod.main(
            [
                "--program", "example",
                "--hash", "h1",
                "--regenerate",
                "--root", str(tmp_path),
            ]
        )

    assert rc == 0


def test_regenerate_provider_unavailable_exits_nonzero(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    _skeleton(paths)

    with patch(
        "earn_money.triage.draft.from_env",
        side_effect=ProviderUnavailable("no key"),
    ):
        rc = draft_mod.main(
            [
                "--program", "example",
                "--hash", "h1",
                "--regenerate",
                "--root", str(tmp_path),
            ]
        )

    assert rc == 1


def test_regenerate_draft_not_found_exits_nonzero(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed(paths)

    with (
        patch("earn_money.triage.draft.from_env", return_value=object()),
        patch(
            "earn_money.triage.draft.polish_draft",
            side_effect=DraftNotFound("not found"),
        ),
    ):
        rc = draft_mod.main(
            [
                "--program", "example",
                "--hash", "h1",
                "--regenerate",
                "--root", str(tmp_path),
            ]
        )

    assert rc == 1


def test_regenerate_structured_output_error_exits_nonzero(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    _skeleton(paths)

    with (
        patch("earn_money.triage.draft.from_env", return_value=object()),
        patch(
            "earn_money.triage.draft.polish_draft",
            side_effect=StructuredOutputError("bad json"),
        ),
    ):
        rc = draft_mod.main(
            [
                "--program", "example",
                "--hash", "h1",
                "--regenerate",
                "--root", str(tmp_path),
            ]
        )

    assert rc == 1
