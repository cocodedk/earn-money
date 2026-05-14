"""Tests for the subzy-based takeover validator runner."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money.recon import assets
from earn_money.recon.signals import Signal
from earn_money.runners import active, takeover_validate


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


def _seed_assets(paths: config.Paths, subdomains: list[str]) -> None:
    conn = db.open_db(paths.program_db("hackerone", "example"))
    obs = [assets.AssetObservation(subdomain=sd, ips=()) for sd in subdomains]
    assets.upsert_assets(conn, obs, observed_at="2026-05-12T07:00:00Z", in_scope=True)
    conn.close()


def _make_signal(host: str, *, service: str = "Heroku") -> Signal:
    return Signal(
        run_id="r",
        tool="subzy",
        signal_type="takeover_vulnerable",
        asset=host,
        target=f"https://{host}/",
        signature=f"subzy|{service.lower()}|{host}",
        payload=json.dumps({"service": service.lower(), "severity": "high"}),
        observed_at="2026-05-14T10:00:00Z",
    )


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])
    with pytest.raises(flags.ReconDisabled):
        takeover_validate.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_refuses_when_policy_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only", in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])
    with pytest.raises(policy.PolicyViolation):
        takeover_validate.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_loads_in_scope_subdomains_explicit_first(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths,
        in_scope=["www.example.com", "dashboard.example.com", "*.example.com"],
    )
    _seed_assets(paths, [
        "alpha.example.com",       # wildcard match
        "www.example.com",         # explicit
        "dashboard.example.com",   # explicit
        "beta.example.com",        # wildcard match
    ])
    captured: list[list[str]] = []

    def fake(targets: list[str]) -> active.ToolRunResult:
        captured.append(list(targets))
        return active.ToolRunResult(outputs=())

    takeover_validate.run_program(
        paths, "hackerone", "example", tool_run=fake, max_targets=4,
    )
    # Explicit (alphabetical) → wildcard-matched (alphabetical).
    assert captured[0] == [
        "dashboard.example.com",
        "www.example.com",
        "alpha.example.com",
        "beta.example.com",
    ]


def test_max_targets_caps_subdomains(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["*.example.com"])
    _seed_assets(paths, [f"shard{i:02d}.example.com" for i in range(10)])
    captured: list[list[str]] = []

    def fake(targets: list[str]) -> active.ToolRunResult:
        captured.append(list(targets))
        return active.ToolRunResult(outputs=())

    takeover_validate.run_program(
        paths, "hackerone", "example", tool_run=fake, max_targets=3,
    )
    assert captured[0] == [
        "shard00.example.com",
        "shard01.example.com",
        "shard02.example.com",
    ]


def test_inserts_in_scope_signals_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def fake(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            _make_signal("api.example.com"),          # in scope
            _make_signal("evil.attacker.com"),        # out of scope
        ))

    result = takeover_validate.run_program(
        paths, "hackerone", "example", tool_run=fake,
    )
    assert result.outputs_recorded == 1
    assert result.oos_drops == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT asset FROM signals WHERE tool = 'subzy'"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]


def test_manifest_records_roe_block(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    takeover_validate.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )

    manifest = json.loads(
        next(
            (paths.root / "recon/outputs/hackerone/example/subzy").rglob("manifest.json")
        ).read_text(encoding="utf-8")
    )
    assert manifest["tool"] == "subzy"
    assert manifest["roe"]["dos_authorized"] is False
    assert manifest["roe"]["max_requests_per_second"] == 10
    assert manifest["roe"]["authorized_test_environments"] == []


def test_cli_returns_6_on_invalid_roe(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: malformed roe.md surfaces as exit 6 with a named-
    error message, same controlled-failure shape as nuclei-scan."""
    from earn_money.runners import takeover_validate_cli
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    roe_path = paths.roe_file("hackerone", "example")
    roe_path.parent.mkdir(parents=True, exist_ok=True)
    roe_path.write_text(
        "---\nmax_requests_per_second: -1\n---\n", encoding="utf-8",
    )
    rc = takeover_validate_cli.main(
        ["--platform", "hackerone", "--program", "example",
         "--root", str(paths.root)]
    )
    assert rc == 6
    assert "invalid roe.md" in capsys.readouterr().err


def test_records_recon_run_row(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    takeover_validate.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT tool, status, input_count, signal_count FROM recon_runs "
        "WHERE tool = 'subzy'"
    ).fetchall()
    conn.close()
    assert rows == [("subzy", "success", 1, 0)]
