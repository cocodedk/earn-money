"""Shared contract for Phase 3 active-recon runners.

Every active runner imports the result dataclass and the gate-check
helper from this module, so the gate order is identical across runners
and the result shape stays consistent for the digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from earn_money import config, flags, policy, scope


@dataclass(frozen=True)
class ActiveRunResult:
    run_id: str
    targets_considered: int = 0
    targets_scanned: int = 0
    artifacts_written: int = 0
    outputs_recorded: int = 0
    source_failures: int = 0
    oos_drops: int = 0
    terminated_reason: Literal["kill_switch", "freeze", "timeout"] | None = None
    prereq_skipped: bool = False
    roe_skipped: bool = False


@dataclass(frozen=True)
class ToolRunResult:
    """Return type for the injected tool_run callable.

    `outputs` is a tuple of parsed observations from the underlying tool:
    `HttpService` for httpx, `Signal` for nuclei / katana / ffuf. The
    runner pulls them out and handles type-specific persistence.
    """
    outputs: tuple[Any, ...] = ()
    aborted: bool = False
    source_failures: int = 0
    timed_out: bool = False
    terminated_reason: Literal["kill_switch", "freeze", "timeout"] | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""


_TerminatedReason = Literal["kill_switch", "freeze", "timeout"]


def resolve_run_status(
    tool_result: ToolRunResult,
) -> tuple[Literal["success", "partial"], _TerminatedReason | None]:
    """Map a ToolRunResult to (run_status, terminated_reason).

    Reason precedence: caller-provided > kill_switch > timeout > None.
    Status is 'partial' if a terminated_reason was resolved OR any
    source_failures occurred; 'success' otherwise.

    terminated_reason is narrowed at ToolRunResult construction time so
    no cast is required here.
    """
    reason: _TerminatedReason | None = (
        tool_result.terminated_reason
        or ("kill_switch" if tool_result.aborted else None)
        or ("timeout" if tool_result.timed_out else None)
    )
    status: Literal["success", "partial"] = (
        "partial" if (reason or tool_result.source_failures > 0)
        else "success"
    )
    return status, reason


def check_gates(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    mode: Literal["passive", "active"],
) -> scope.Scope:
    """Run the four pre-flight gates in canonical order and return the
    program's resolved scope on success. Any failure raises a typed
    exception that the runner's main() translates to an exit code."""
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)
    s = scope.read_scope(paths.scope_file(platform, slug))
    policy.require_policy_allows(s, mode=mode)
    return s
