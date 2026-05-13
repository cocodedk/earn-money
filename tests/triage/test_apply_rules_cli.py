from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import db
from earn_money.triage import apply_rules_cli, findings
from tests.triage.conftest import engine_paths, make_finding


def _seed_rules(paths: object, vuln_class: str = "csp") -> None:
    (paths.root / "triage_rules.yaml").write_text(  # type: ignore[attr-defined]
        "rules:\n"
        f"  - name: noise.{vuln_class}\n"
        f"    vuln_class: {vuln_class}\n"
        "    severity: info\n"
        "    reason: playbook-noise\n",
        encoding="utf-8",
    )


def _insert(paths: object, finding_hash: str, vuln_class: str, severity: str) -> None:
    f = make_finding(
        finding_hash=finding_hash,
        vuln_class=vuln_class,
        severity_hint=severity,
        notes_path=f"findings/_queue/{finding_hash}.md",
    )
    conn = db.open_db(paths.program_db("hackerone", "example"))  # type: ignore[attr-defined]
    try:
        findings.upsert_finding(conn, f)
    finally:
        conn.close()


def _run(root: Path, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = apply_rules_cli.main(["--root", str(root), *argv])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_apply_rules_transitions_matching_queued_finding(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _seed_rules(paths, vuln_class="csp")
    fh = "c" * 64
    _insert(paths, fh, vuln_class="csp", severity="info")

    rc, out, _ = _run(paths.root, ["--program", "example"], capsys)
    assert rc == 0
    assert "applied=1" in out

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        state, = conn.execute(
            "SELECT current_state FROM findings WHERE finding_hash=?", (fh,)
        ).fetchone()
        notes = conn.execute(
            "SELECT actor, to_state, note FROM findings_state_history "
            "WHERE finding_hash=?", (fh,),
        ).fetchall()
    finally:
        conn.close()
    assert state == "resolved_info"
    assert len(notes) == 1
    actor, to_state, note = notes[0]
    assert actor == "triage-engine"
    assert to_state == "resolved_info"
    assert "rule=noise.csp" in note
    assert "template=csp" in note
    assert "reason=playbook-noise" in note


def test_apply_rules_leaves_non_matching_finding_queued(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _seed_rules(paths, vuln_class="csp")
    fh = "d" * 64
    _insert(paths, fh, vuln_class="open-redirect", severity="info")

    rc, out, _ = _run(paths.root, ["--program", "example"], capsys)
    assert rc == 0
    assert "applied=0" in out

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        state, = conn.execute(
            "SELECT current_state FROM findings WHERE finding_hash=?", (fh,)
        ).fetchone()
        n_history = conn.execute(
            "SELECT COUNT(*) FROM findings_state_history WHERE finding_hash=?", (fh,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert state == "queued"
    assert n_history == 0


def test_apply_rules_dry_run_makes_no_changes(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    _seed_rules(paths, vuln_class="csp")
    fh = "e" * 64
    _insert(paths, fh, vuln_class="csp", severity="info")

    rc, out, _ = _run(paths.root, ["--program", "example", "--dry-run"], capsys)
    assert rc == 0
    assert "dry_run=True" in out
    assert "would transition" in out.lower()

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        state, = conn.execute(
            "SELECT current_state FROM findings WHERE finding_hash=?", (fh,)
        ).fetchone()
        n_history = conn.execute(
            "SELECT COUNT(*) FROM findings_state_history WHERE finding_hash=?", (fh,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert state == "queued"  # no changes
    assert n_history == 0


def test_apply_rules_unregistered_program_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, _, err = _run(paths.root, ["--program", "does-not-exist"], capsys)
    assert rc == 1
    assert "not registered" in err.lower()
