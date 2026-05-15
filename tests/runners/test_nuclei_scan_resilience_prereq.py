"""Prereq-missing and terminated_reason tests for the nuclei-scan runner."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from earn_money import config, db, scope
from earn_money._time import to_iso
from earn_money.recon import services
from earn_money.runners import active, nuclei_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService]
) -> None:
    """Seed a fresh successful httpx run + matching http_services rows so
    nuclei can see a recent prereq. Timestamps are wall-clock-relative so
    the runner's 24h prereq freshness window always holds."""
    from earn_money.recon import runs
    now = datetime.now(UTC)
    started_at = to_iso(now - timedelta(minutes=5))
    finished_at = to_iso(now - timedelta(minutes=1))
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at=started_at,
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at=finished_at,
            status="success", output_count=len(services_to_insert),
            signal_count=0, source_failures=0, oos_drops=0,
        )
        for svc in services_to_insert:
            services.upsert_service(conn, svc)
    finally:
        conn.close()


def test_prereq_missing_still_writes_required_artifacts(tmp_repo: Path) -> None:
    """record_prereq_missing must write all 5 required artifacts so the
    artifact contract holds even for skipped runs."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = nuclei_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    assert result.outputs_recorded == 0  # tool produced no outputs; audit signal lives in DB
    assert result.prereq_skipped is True

    nuclei_out = paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei"
    for name in ("manifest.json", "signals.jsonl", "input.txt", "raw.jsonl", "stderr.txt"):
        files = list(nuclei_out.rglob(name))
        assert len(files) == 1, f"missing required artifact: {name}"


def test_terminated_reason_in_result_matches_recon_runs_row(tmp_repo: Path) -> None:
    """ActiveRunResult.terminated_reason must match the terminated_reason
    written to the recon_runs row. When the tool reports an abort, the
    in-memory return and the DB row both carry the same reason."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(
        paths,
        services_to_insert=[
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title=None,
                server=None, technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
            ),
        ],
    )

    def aborted_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(), aborted=True)

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=aborted_tool,
    )
    # In-memory result must carry the reason.
    assert result.terminated_reason == "kill_switch"

    # DB row must carry the same reason.
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT terminated_reason FROM recon_runs WHERE tool='nuclei'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "kill_switch"
