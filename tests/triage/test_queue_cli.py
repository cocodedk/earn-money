from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import db
from earn_money.triage import findings, queue_cli
from tests.triage.conftest import engine_paths, make_finding


def _run(
    root: Path, argv: list[str], capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    rc = queue_cli.main(["--root", str(root), *argv])
    return rc, capsys.readouterr().out


def _seed(
    paths: object, items: list[tuple[str, str, str]],
) -> None:
    """Insert queued findings with (finding_hash, severity_hint, first_seen)."""
    conn = db.open_db(paths.program_db("hackerone", "example"))  # type: ignore[attr-defined]
    try:
        for fh, sev, fs in items:
            findings.upsert_finding(
                conn,
                make_finding(
                    finding_hash=fh,
                    severity_hint=sev,
                    first_seen=fs,
                    last_seen=fs,
                    state_changed_at=fs,
                    notes_path=f"findings/_queue/{fh}.md",
                ),
            )
    finally:
        conn.close()


def test_queue_empty_prints_no_findings_message(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, out = _run(paths.root, ["--program", "example"], capsys)
    assert rc == 0
    assert "no queued findings" in out.lower()


def test_queue_default_top_5_sorted(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _seed(paths, [
        ("a" * 64, "high",     "2026-05-12T04:00:00Z"),
        ("b" * 64, "critical", "2026-05-12T05:00:00Z"),
        ("c" * 64, "high",     "2026-05-12T03:00:00Z"),  # older 'high'
        ("d" * 64, "info",     "2026-05-12T06:00:00Z"),  # info shouldn't appear in top 5
        ("e" * 64, "low",      "2026-05-12T07:00:00Z"),
        ("f" * 64, "medium",   "2026-05-12T08:00:00Z"),
        ("g" * 64, "info",     "2026-05-12T09:00:00Z"),
    ])
    rc, out = _run(paths.root, ["--program", "example"], capsys)
    assert rc == 0
    body_rows = [ln for ln in out.splitlines() if ln and not ln.startswith(("hash", "-"))]
    assert len(body_rows) == 5
    sevs = [ln.split()[1] for ln in body_rows]
    assert sevs == ["critical", "high", "high", "medium", "low"]
    # tie-break: the older 'high' (cccccccc) sorts ahead of the newer (aaaaaaaa)
    hashes = [ln.split()[0] for ln in body_rows]
    assert hashes[1] == "c" * 8
    assert hashes[2] == "a" * 8


def test_queue_unknown_program_prints_error_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)  # only registers 'example'
    rc = queue_cli.main([
        "--root", str(paths.root), "--program", "does-not-exist",
    ])
    captured = capsys.readouterr()
    assert rc == 1
    assert "queue:" in captured.err.lower()


def test_queue_all_shows_full_backlog(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _seed(paths, [
        ("a" * 64, "high",     "2026-05-12T04:00:00Z"),
        ("b" * 64, "critical", "2026-05-12T05:00:00Z"),
        ("c" * 64, "high",     "2026-05-12T03:00:00Z"),
        ("d" * 64, "info",     "2026-05-12T06:00:00Z"),
        ("e" * 64, "low",      "2026-05-12T07:00:00Z"),
        ("f" * 64, "medium",   "2026-05-12T08:00:00Z"),
        ("g" * 64, "info",     "2026-05-12T09:00:00Z"),
    ])
    rc, out = _run(paths.root, ["--program", "example", "--all"], capsys)
    assert rc == 0
    body_rows = [ln for ln in out.splitlines() if ln and not ln.startswith(("hash", "-"))]
    sevs = [ln.split()[1] for ln in body_rows]
    assert sevs == ["critical", "high", "high", "medium", "low", "info", "info"]
