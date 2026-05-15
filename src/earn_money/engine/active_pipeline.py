"""Sequential active-pipeline orchestrator for a single program.

Runs the five active-mode runners in order:
    httpx-probe → nuclei-scan → takeover-validate → sourcemap-scan
                → katana-crawl → graphql-probe

Each step calls its runner's `run_program` directly. The pipeline
short-circuits on a gate failure (RECON_ENABLED missing, FROZEN
flag, policy violation) — none of the active runners ever fire for
that program until the operator clears the gate. Tool-level failures
(httpx returning zero services, nuclei timing out a batch) do NOT
short-circuit; subsequent steps still run because they read from
the DB, not from the previous step's in-memory result.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from earn_money import config, flags, policy, roe, scope
from earn_money.runners import (
    active,
    auth_bypass_probe,
    graphql_probe,
    httpx_probe,
    katana_crawl,
    nuclei_scan,
    sourcemap_scan,
    sqli_probe,
    takeover_validate,
    xss_probe,
)

if TYPE_CHECKING:
    from earn_money.agent.decider import AgentDecider  # type-only; no runtime cycle

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


# Tuple-of-(name, run_program-callable) keeps step order explicit and
# lets `run_program_pipeline` enumerate them without copy-paste.
_PIPELINE: tuple[tuple[str, Callable[..., active.ActiveRunResult]], ...] = (
    ("httpx-probe", httpx_probe.run_program),
    ("nuclei-scan", nuclei_scan.run_program),
    ("takeover-validate", takeover_validate.run_program),
    ("sourcemap-scan", sourcemap_scan.run_program),
    ("katana-crawl", katana_crawl.run_program),
    ("graphql-probe", graphql_probe.run_program),
    ("auth-bypass-probe", auth_bypass_probe.run_program),
    ("sqli-probe", sqli_probe.run_program),
    ("xss-probe", xss_probe.run_program),
)


_PIPELINE_BY_NAME = dict(_PIPELINE)


def run_program_pipeline(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_factory: Callable[[str, config.Paths, str, str, str], ToolRun],
    max_targets_per_step: int | None = None,
    decider: AgentDecider | None = None,
) -> PipelineResult:
    """Run active runners for `(platform, slug)`.

    Without `decider`: iterate `_PIPELINE` in fixed order (current behavior).
    With `decider`: ask it for the next step between iterations; the
    orchestrator validates that the chosen name is in `_PIPELINE_BY_NAME`
    and refuses anything else. Decider may also override `max_targets`
    per step and request a `stop`.
    """
    abort = _gate_check(paths, platform, slug)
    if abort is not None:
        return PipelineResult(
            platform=platform, slug=slug, steps=(), aborted_reason=abort,
        )

    steps: list[StepResult] = []
    pending = [name for name, _ in _PIPELINE]
    for _ in range(len(_PIPELINE)):
        name, max_targets = _pick_next(
            pending, steps, paths, platform, slug, decider, max_targets_per_step,
        )
        if name is None:
            break
        run_program = _PIPELINE_BY_NAME[name]
        run_id = uuid.uuid4().hex
        try:
            tool_run = tool_factory(name, paths, platform, slug, run_id)
            result = run_program(
                paths, platform, slug,
                tool_run=tool_run, run_id=run_id, max_targets=max_targets,
            )
        except (flags.ReconDisabled, flags.ProgramFrozen, roe.InvalidRoE) as exc:
            return PipelineResult(
                platform=platform, slug=slug, steps=tuple(steps),
                aborted_reason=f"{type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            steps.append(StepResult(
                runner=name, status="failed",
                detail=f"{type(exc).__name__}: {exc}",
            ))
            if name in pending:
                pending.remove(name)
            continue
        if name in pending:
            pending.remove(name)
        if getattr(result, "prereq_skipped", False):
            steps.append(StepResult(
                runner=name, status="skipped", detail="prereq missing",
            ))
            continue
        steps.append(StepResult(
            runner=name, status="ok",
            outputs_recorded=result.outputs_recorded,
        ))
    return PipelineResult(platform=platform, slug=slug, steps=tuple(steps))


def _pick_next(
    pending: list[str],
    completed: list[StepResult],
    paths: config.Paths,
    platform: str,
    slug: str,
    decider: AgentDecider | None,
    default_max_targets: int | None,
) -> tuple[str | None, int | None]:
    """Return (step_name, max_targets) for the next runner, or (None, _)
    to stop the pipeline. With `decider=None`, picks the first pending
    step in fixed order."""
    if not pending:
        return None, None
    if decider is None:
        return pending[0], default_max_targets
    decision = decider(
        paths, platform, slug, completed_steps=tuple(completed),
    )
    if decision.next_step == "stop":
        return None, None
    if decision.next_step not in _PIPELINE_BY_NAME or decision.next_step not in pending:
        # Decider returned an unknown or already-completed step — fall back to
        # the next pending step rather than crashing or looping the pipeline.
        return pending[0], default_max_targets
    return decision.next_step, decision.max_targets or default_max_targets
