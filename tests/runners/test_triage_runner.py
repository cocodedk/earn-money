from __future__ import annotations

from pathlib import Path

from earn_money import config, scope
from earn_money.runners import triage


def _seed(tmp_repo: Path, *, recon_enabled: bool = True) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    if recon_enabled:
        paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    return paths


def test_returns_zero_when_no_runs_to_triage(tmp_repo: Path) -> None:
    _seed(tmp_repo)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0


def test_returns_kill_switch_code_when_recon_disabled(tmp_repo: Path) -> None:
    _seed(tmp_repo, recon_enabled=False)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 2


def test_runs_for_manual_only_program(tmp_repo: Path) -> None:
    """Triage produces no target traffic, so it MUST run for manual-only programs
    (the operator may have hand-fed signals into the DB)."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="manual-only",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0
