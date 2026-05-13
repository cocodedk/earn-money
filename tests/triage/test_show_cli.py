from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import db
from earn_money.triage import findings, show_cli
from tests.triage.conftest import engine_paths, make_finding


def _run(
    root: Path, argv: list[str], capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    rc = show_cli.main(["--root", str(root), *argv])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def _insert(paths: object, finding_hash: str) -> None:
    f = make_finding(
        finding_hash=finding_hash,
        notes_path=f"findings/_queue/{finding_hash}.md",
    )
    conn = db.open_db(paths.program_db("hackerone", "example"))  # type: ignore[attr-defined]
    try:
        findings.upsert_finding(conn, f)
    finally:
        conn.close()


def test_show_prints_body_and_history(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    finding_hash = "a" * 8 + "1" + "0" * 55
    _insert(paths, finding_hash)
    body_path = paths.root / f"findings/_queue/{finding_hash}.md"
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text("BODY-OF-FINDING\n", encoding="utf-8")

    rc, out, _ = _run(paths.root, ["--program", "example", finding_hash[:8]], capsys)
    assert rc == 0
    assert "BODY-OF-FINDING" in out
    assert "audit history" in out.lower()


def test_show_ambiguous_prefix_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _insert(paths, "a" * 8 + "1" + "0" * 55)
    _insert(paths, "a" * 8 + "2" + "0" * 55)
    rc, _, err = _run(paths.root, ["--program", "example", "a" * 8], capsys)
    assert rc == 1
    assert "ambiguous" in err.lower()


def test_show_missing_prefix_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, _, err = _run(paths.root, ["--program", "example", "deadbeef"], capsys)
    assert rc == 1
    assert "no finding" in err.lower()


def test_show_wildcard_prefix_does_not_match_literally(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """`%` and `_` must NOT act as SQL LIKE wildcards on operator input."""
    paths = engine_paths(tmp_repo)
    _insert(paths, "a" * 8 + "1" + "0" * 55)
    rc, _, err = _run(paths.root, ["--program", "example", "%"], capsys)
    assert rc == 1
    assert "no finding" in err.lower()


def test_show_unregistered_program_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, _, err = _run(paths.root, ["--program", "does-not-exist", "deadbeef"], capsys)
    assert rc == 1
    assert "not registered" in err.lower()
