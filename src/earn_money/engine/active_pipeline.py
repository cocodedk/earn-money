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
from typing import TYPE_CHECKING

from earn_money import config, db, flags, roe
from earn_money.recon import runs

from ._active_pipeline_registry import _PIPELINE, _PIPELINE_BY_NAME, _pick_next
from ._active_pipeline_steps import PipelineResult, StepResult, ToolRun, _gate_check

if TYPE_CHECKING:
    from earn_money.agent.decider import AgentDecider  # type-only; no runtime cycle


# Re-export the public surface so existing importers
# (`from earn_money.engine.active_pipeline import StepResult`) keep working.
__all__ = [
    "PipelineResult",
    "StepResult",
    "ToolRun",
    "run_program_pipeline",
]


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

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        runs.cleanup_stale_runs(conn, platform=platform, slug=slug)
    finally:
        conn.close()

    steps: list[StepResult] = []
    pending = [name for name, _ in _PIPELINE]
    for _ in range(len(_PIPELINE) * 2):  # allow each step up to 2 tries (prereq retry)
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
        if getattr(result, "prereq_skipped", False):
            steps.append(StepResult(
                runner=name, status="skipped", detail="prereq missing",
            ))
            # Rotate to end so the step is retried after its prereq runs.
            if name in pending:
                pending.remove(name)
                pending.append(name)
            continue
        if getattr(result, "roe_skipped", False):
            if name in pending:
                pending.remove(name)
            steps.append(StepResult(
                runner=name, status="skipped", detail="roe not authorized",
            ))
            continue
        if name in pending:
            pending.remove(name)
        steps.append(StepResult(
            runner=name, status="ok",
            outputs_recorded=result.outputs_recorded,
        ))
    return PipelineResult(platform=platform, slug=slug, steps=tuple(steps))
