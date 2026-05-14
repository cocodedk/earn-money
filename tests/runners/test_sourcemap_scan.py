"""Tests for the sourcemap-scan runner."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money._time import to_iso
from earn_money.recon import runs, services
from earn_money.recon.signals import Signal
from earn_money.runners import active, sourcemap_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["api.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService],
) -> None:
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


def _service(host: str) -> services.HttpService:
    return services.HttpService(
        subdomain=host, scheme="https", port=443,
        url=f"https://{host}/", status_code=200, title=None,
        server=None, technologies=(), redirect_to=None, tls_summary=None,
        observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
    )


def _signal(host: str) -> Signal:
    return Signal(
        run_id="r", tool="sourcemap-scan", signal_type="leaked_secret",
        asset=host, target=f"https://{host}/static/app.js",
        signature="sourcemap|aws_access_key|AKIA…LE",
        payload=json.dumps({"pattern": "aws_access_key", "severity": "high"}),
        observed_at="2026-05-14T12:00:00Z",
    )


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[_service("api.example.com")])
    with pytest.raises(flags.ReconDisabled):
        sourcemap_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_refuses_when_policy_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only", in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[_service("api.example.com")])
    with pytest.raises(policy.PolicyViolation):
        sourcemap_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_prereq_missing_writes_skipped_run(tmp_repo: Path) -> None:
    """No recent httpx success → status='skipped', prereq_skipped=True."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = sourcemap_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )
    assert result.prereq_skipped is True

    out_dir = paths.root / "recon/outputs/hackerone/example/sourcemap"
    for name in ("manifest.json", "signals.jsonl", "input.txt"):
        assert list(out_dir.rglob(name)), f"missing {name}"


def test_inserts_in_scope_signals_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[_service("api.example.com")])

    def fake(_t: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            _signal("api.example.com"),       # in scope
            _signal("evil.attacker.com"),     # out of scope
        ))

    result = sourcemap_scan.run_program(
        paths, "hackerone", "example", tool_run=fake,
    )
    assert result.outputs_recorded == 1
    assert result.oos_drops == 1


def test_manifest_records_roe_block(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[_service("api.example.com")])

    sourcemap_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )

    manifest = json.loads(
        next(
            (paths.root / "recon/outputs/hackerone/example/sourcemap").rglob("manifest.json")
        ).read_text(encoding="utf-8")
    )
    assert manifest["tool"] == "sourcemap-scan"
    assert manifest["roe"]["dos_authorized"] is False
    assert manifest["roe"]["max_requests_per_second"] == 10


def test_records_recon_run_row(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[_service("api.example.com")])

    sourcemap_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT tool, status, input_count, signal_count FROM recon_runs "
        "WHERE tool = 'sourcemap-scan'"
    ).fetchall()
    conn.close()
    assert rows == [("sourcemap-scan", "success", 1, 0)]
