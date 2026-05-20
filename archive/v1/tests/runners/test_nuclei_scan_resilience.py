"""Resilience tests for the nuclei-scan runner: partial status, source_failures,
artifact contract, and terminated_reason propagation."""

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


def test_source_failures_promotes_run_to_partial(tmp_repo: Path) -> None:
    """A scan that completes without abort but has nonzero source_failures
    (e.g. some batches returned non-zero exit) must record status='partial'
    so the digest surfaces the partial result instead of reporting clean."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def flaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(), source_failures=2)

    nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=flaky_tool,
    )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT status, source_failures FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert rows == [("partial", 2)]


def test_source_failures_record_stderr_tail_in_error_summary(tmp_repo: Path) -> None:
    """When a batch fails with non-zero return code, surface its stderr tail
    in recon_runs.error_summary so the operator can diagnose without
    re-running the tool by hand."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def flaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=(),
            source_failures=1,
            raw_stderr="ERR: nuclei panicked at templates/foo.yaml\n",
        )

    nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=flaky_tool,
    )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    err_summary, = conn.execute(
        "SELECT error_summary FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchone()
    conn.close()
    assert err_summary is not None
    assert "1 batch" in err_summary
    assert "nuclei panicked at templates/foo.yaml" in err_summary


def test_source_failures_empty_stderr_still_records_error_summary(
    tmp_repo: Path,
) -> None:
    """The cycle-1 case: batch exits non-zero with no stderr output. The
    empty-stderr fact itself is diagnostic — must not be silent."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def silent_failing_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(), source_failures=1, raw_stderr="")

    nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=silent_failing_tool,
    )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    err_summary, = conn.execute(
        "SELECT error_summary FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchone()
    conn.close()
    assert err_summary is not None
    assert "(empty stderr)" in err_summary


