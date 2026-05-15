"""Tests for triage engine: multi-run processing and suppression routing."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import runs, services, signals
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
from earn_money.triage import engine
from tests.triage.conftest import engine_paths, seed_nuclei_run_with_signal


def _seed_nuclei_run_with_suppressible_signal(paths: object) -> None:
    """Seed a nuclei run with a CSP wildcard signal that matches the
    noise.csp suppression rule."""
    conn = db.open_db(paths.program_db("hackerone", "example"))  # type: ignore[attr-defined]
    try:
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r1", finished_at="2026-05-12T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/",
            signature="csp-script-src-wildcard|primary|",
            payload=(
                '{"template_id":"csp-script-src-wildcard",'
                '"severity":"info","name":"CSP wildcard"}'
            ),
            observed_at="2026-05-12T02:16:00Z",
        )])
        conn.commit()
    finally:
        conn.close()


def test_triages_all_untriaged_runs_and_marks_them(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    seed_nuclei_run_with_signal(paths)
    # Add a second nuclei run with a different finding.
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T03:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-12T03:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="www.example.com",
            target="https://www.example.com/login",
            signature="http-default-creds|admin-admin|",
            payload='{"template_id":"http-default-creds","severity":"high",'
                    '"name":"Default admin/admin"}',
            observed_at="2026-05-12T03:17:00Z",
        )])
    finally:
        conn.close()

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.runs_processed == 2
    assert result.findings_created == 2

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    try:
        triaged = conn.execute(
            "SELECT run_id, triaged_at FROM recon_runs ORDER BY run_id"
        ).fetchall()
    finally:
        conn.close()
    assert all(row[1] == "2026-05-12T05:00:00Z" for row in triaged)


def test_engine_routes_suppressed_finding_to_resolved_info(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    (paths.root / "triage_rules.yaml").write_text(
        "rules:\n"
        "  - name: noise.csp\n"
        "    vuln_class: csp-script-src-wildcard\n"
        "    severity: info\n"
        "    reason: playbook-noise\n",
        encoding="utf-8",
    )
    _seed_nuclei_run_with_suppressible_signal(paths)

    engine.run_program(paths, "hackerone", "example", now="2026-05-12T05:00:00Z")

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    try:
        finding_hash, state, notes_path = conn.execute(
            "SELECT finding_hash, current_state, notes_path FROM findings"
        ).fetchone()
        hist = conn.execute(
            "SELECT to_state, actor, note FROM findings_state_history "
            "WHERE finding_hash = ?",
            (finding_hash,),
        ).fetchall()
    finally:
        conn.close()

    assert state == "resolved_info"
    assert notes_path == f"findings/_resolved/info/{finding_hash}.md"
    assert not (paths.root / "findings" / "_queue" / f"{finding_hash}.md").exists()
    assert (
        paths.root / "findings" / "_resolved" / "info" / f"{finding_hash}.md"
    ).exists()
    assert len(hist) == 1
    to_state, actor, note = hist[0]
    assert to_state == "resolved_info"
    assert actor == "triage-engine"
    assert note.startswith("rule=noise.csp template=csp-script-src-wildcard ")
    assert "reason=playbook-noise" in note
