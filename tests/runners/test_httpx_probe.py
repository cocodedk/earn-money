"""Tests for the httpx_probe active-recon runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, flags, policy, scope
from earn_money.recon import services
from earn_money.runners import active, httpx_probe


def _seed(
    paths: config.Paths,
    *,
    in_scope: list[str],
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=in_scope, out_of_scope=out_of_scope or [], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_assets(paths: config.Paths, subdomains: list[str]) -> None:
    from earn_money import db
    from earn_money.recon import assets
    conn = db.open_db(paths.program_db("hackerone", "example"))
    obs = [assets.AssetObservation(subdomain=sd, ips=()) for sd in subdomains]
    assets.upsert_assets(conn, obs, observed_at="2026-05-12T07:00:00Z", in_scope=True)
    conn.close()


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com"])
    with pytest.raises(flags.ReconDisabled):
        httpx_probe.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="manual-only",
        in_scope=["*.example.com"], out_of_scope=[], notes="",
        scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    with pytest.raises(policy.PolicyViolation):
        httpx_probe.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_writes_services_for_in_scope_assets(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com", "www.example.com"])

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=tuple(
            services.HttpService(
                subdomain=t, scheme="https", port=443,
                url=f"https://{t}/", status_code=200, title="ok",
                server="nginx", technologies=("nginx",),
                redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            )
            for t in targets
        ))

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=fake_tool,
    )
    assert result.targets_scanned == 2
    assert result.artifacts_written == 1  # one manifest written
    # outputs_recorded reflects what was actually persisted, not inputs.
    # Real httpx silently drops unreachable hosts; the CLI needs the real
    # count to be honest with the operator.
    assert result.outputs_recorded == 2

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services ORDER BY subdomain").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com", "www.example.com"]


def test_outputs_recorded_smaller_than_targets_when_tool_silently_drops(
    tmp_repo: Path,
) -> None:
    """Real httpx silently drops unreachable hosts; outputs_recorded
    reflects that drop, even though targets_scanned does not."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["a.example.com", "b.example.com", "c.example.com"])

    def half_alive_tool(targets: list[str]) -> active.ToolRunResult:
        # Only 1/3 of targets respond — simulating unreachable hosts.
        return active.ToolRunResult(outputs=(
            services.HttpService(
                subdomain="a.example.com", scheme="https", port=443,
                url="https://a.example.com/", status_code=200, title="ok",
                server="nginx", technologies=("nginx",),
                redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            ),
        ))

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=half_alive_tool,
    )
    assert result.targets_scanned == 3
    assert result.outputs_recorded == 1  # the real, honest count


def test_drops_out_of_scope_targets_from_tool_output(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title="",
                server="nginx", technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            ),
            services.HttpService(
                subdomain="evil.example.com", scheme="https", port=443,
                url="https://evil.example.com/", status_code=200, title="",
                server="nginx", technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            ),
        ))

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]


def test_freeze_mid_run_records_freeze_terminated_reason(tmp_repo: Path) -> None:
    """If tool_run returns aborted=True with terminated_reason='freeze',
    the runner records 'freeze' in recon_runs.terminated_reason — not
    the generic 'kill_switch'."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def freezing_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=(), aborted=True, terminated_reason="freeze",
        )

    result = httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=freezing_tool,
    )
    assert result.terminated_reason == "freeze"

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT status, terminated_reason FROM recon_runs"
    ).fetchone()
    conn.close()
    assert row == ("partial", "freeze")


def test_records_failed_run_when_tool_raises(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def broken_tool(_targets: list[str]) -> active.ToolRunResult:
        raise RuntimeError("simulated tool crash")

    with pytest.raises(RuntimeError, match="simulated"):
        httpx_probe.run_program(
            paths, "hackerone", "example", tool_run=broken_tool,
        )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT status, error_summary FROM recon_runs"
    ).fetchall()
    conn.close()
    assert rows == [("failed", "RuntimeError: simulated tool crash")]
