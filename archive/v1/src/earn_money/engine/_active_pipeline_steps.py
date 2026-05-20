"""Step-level dataclasses and gate-check helper for active pipeline.

Extracted from `active_pipeline` to keep that orchestrator file under
the project's 200-line cap. Public surface is re-exported by the
facade module — importers should continue to use `active_pipeline`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from earn_money import config, flags, policy, roe, scope
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]


@dataclass(frozen=True)
class StepResult:
    runner: str
    status: str  # "ok" | "skipped" | "failed"
    detail: str = ""
    outputs_recorded: int = 0


@dataclass(frozen=True)
class PipelineResult:
    platform: str
    slug: str
    steps: tuple[StepResult, ...]
    aborted_reason: str | None = None


def _gate_check(
    paths: config.Paths, platform: str, slug: str,
) -> str | None:
    """Run the four pre-flight gates without launching any runner.

    Returns a short reason string on first failure, or None to proceed.
    """
    try:
        active.check_gates(paths, platform, slug, mode="active")
    except flags.ReconDisabled:
        return "kill_switch"
    except flags.ProgramFrozen:
        return "frozen"
    except policy.PolicyViolation as exc:
        return f"policy:{exc}"
    except (scope.InvalidScope, roe.InvalidRoE) as exc:
        return f"config:{type(exc).__name__}"
    return None
