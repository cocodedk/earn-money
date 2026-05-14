"""Tests for the httpx_probe active-recon runner."""

from __future__ import annotations

import json
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


def _make_service(
    subdomain: str,
    *,
    title: str = "ok",
    technologies: tuple[str, ...] = ("nginx",),
) -> services.HttpService:
    """Build an HttpService with the boilerplate fields filled in."""
    return services.HttpService(
        subdomain=subdomain, scheme="https", port=443,
        url=f"https://{subdomain}/", status_code=200, title=title,
        server="nginx", technologies=technologies,
        redirect_to=None, tls_summary=None,
        observed_at="t", last_run_id="r", in_scope_at_observation=True,
    )


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


def test_explicit_scope_entries_sort_before_wildcard_matches(tmp_repo: Path) -> None:
    """Sampling sorts program-authored entries (literal scope.md hostnames)
    before wildcard-resolved fan-out. Drove this bug when algolia's
    *.algolia.net resolved to 27k cluster shards: --max-targets 5 picked
    c3-eu-1..c3-eu-5 (internal shards, 0 services) instead of the
    operator-facing www.algolia.com + dashboard.algolia.com."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    # Scope has TWO explicit hosts + one wildcard.
    _seed(paths, in_scope=["www.algolia.com", "dashboard.algolia.com", "*.algolia.net"])
    _seed_assets(paths, [
        "c3-eu-1.algolia.net", "c3-eu-2.algolia.net", "c3-eu-3.algolia.net",
        "dashboard.algolia.com", "www.algolia.com",
    ])
    captured: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured.append(list(targets))
        return active.ToolRunResult(outputs=())

    httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=fake_tool, max_targets=2,
    )
    # Explicit entries (alphabetically dashboard < www) come first, both
    # picked under the cap of 2; the wildcard-matched shards are skipped.
    assert captured[0] == ["dashboard.algolia.com", "www.algolia.com"]


def test_max_targets_caps_in_scope_assets(tmp_repo: Path) -> None:
    """When wildcards resolve to many assets, --max-targets N slices the
    target list to the first N alphabetical. Discovered when algolia's
    *.algolia.net resolved to 27,808 cluster shards."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, [f"shard{i:02d}.example.com" for i in range(10)])
    captured: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured.append(list(targets))
        return active.ToolRunResult(
            outputs=tuple(_make_service(t) for t in targets),
        )

    httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=fake_tool, max_targets=3,
    )
    assert len(captured) == 1
    assert captured[0] == [
        "shard00.example.com", "shard01.example.com", "shard02.example.com",
    ]


def test_writes_services_for_in_scope_assets(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com", "www.example.com"])

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=tuple(_make_service(t) for t in targets),
        )

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

    def half_alive_tool(_targets: list[str]) -> active.ToolRunResult:
        # Only 1/3 of targets respond — simulating unreachable hosts.
        return active.ToolRunResult(outputs=(_make_service("a.example.com"),))

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
            _make_service("api.example.com", title="", technologies=()),
            _make_service("evil.example.com", title="", technologies=()),
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


def test_manifest_records_roe_under_which_probe_ran(tmp_repo: Path) -> None:
    """The probe's manifest carries an `roe` block so the post-run audit
    trail shows what authority the probe operated under, even when the
    program has no roe.md (floor applies)."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=tuple(_make_service(t) for t in targets),
        )

    httpx_probe.run_program(paths, "hackerone", "example", tool_run=fake_tool)

    manifest_path = next(
        (paths.root / "recon" / "outputs" / "hackerone" / "example" / "httpx").rglob(
            "manifest.json"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["roe"] == {
        "dos_authorized": False,
        "destructive_payloads_authorized": False,
        "social_engineering_authorized": False,
        "pii_handling": "one_redacted_screenshot",
        "max_requests_per_second": 10,
    }
