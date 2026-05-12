"""Tests for the httpx_probe active-recon runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, flags, policy, scope
from earn_money.recon import services
from earn_money.runners import httpx_probe


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
            tool_run=lambda _targets: [],
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
            tool_run=lambda _targets: [],
        )


def test_writes_services_for_in_scope_assets(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com", "www.example.com"])

    def fake_tool(targets: list[str]) -> list[services.HttpService]:
        return [
            services.HttpService(
                subdomain=t, scheme="https", port=443,
                url=f"https://{t}/", status_code=200, title="ok",
                server="nginx", technologies=("nginx",),
                redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            )
            for t in targets
        ]

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=fake_tool,
    )
    assert result.targets_scanned == 2
    assert result.artifacts_written == 1  # one manifest written

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services ORDER BY subdomain").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com", "www.example.com"]


def test_drops_out_of_scope_targets_from_tool_output(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def leaky_tool(_targets: list[str]) -> list[services.HttpService]:
        return [
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
        ]

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]
