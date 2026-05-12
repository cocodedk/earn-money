from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, flags, policy, scope
from earn_money.runners import active


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def test_check_gates_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        active.check_gates(paths, "hackerone", "example", mode="active")


def test_check_gates_refuses_manual_only_policy(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        active.check_gates(paths, "hackerone", "example", mode="active")


def test_check_gates_returns_scope_on_success(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    s = active.check_gates(paths, "hackerone", "example", mode="active")
    assert s.policy == "rate-limited-OK"
    assert s.in_scope == ["*.example.com"]


def test_run_result_defaults_are_zero() -> None:
    r = active.ActiveRunResult(run_id="r")
    assert r.targets_considered == 0
    assert r.targets_scanned == 0
    assert r.artifacts_written == 0
    assert r.signals_emitted == 0
    assert r.source_failures == 0
    assert r.oos_drops == 0
    assert r.terminated_reason is None


def test_check_gates_refuses_frozen_program(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    flags.freeze_program(paths, "hackerone", "example", reason="scope destructive diff")
    _seed_scope(paths)
    with pytest.raises(flags.ProgramFrozen):
        active.check_gates(paths, "hackerone", "example", mode="active")


def test_tool_run_result_terminated_reason_is_typed() -> None:
    """The terminated_reason field accepts only kill_switch/freeze/timeout/None."""
    r1 = active.ToolRunResult(terminated_reason=None)
    r2 = active.ToolRunResult(terminated_reason="kill_switch")
    r3 = active.ToolRunResult(terminated_reason="freeze")
    r4 = active.ToolRunResult(terminated_reason="timeout")
    assert r1.terminated_reason is None
    assert r2.terminated_reason == "kill_switch"
    assert r3.terminated_reason == "freeze"
    assert r4.terminated_reason == "timeout"
