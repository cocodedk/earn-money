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

from earn_money import config, flags, policy, roe, scope
from earn_money.runners import (
    active,
    graphql_probe,
    httpx_probe,
    katana_crawl,
    nuclei_scan,
    sourcemap_scan,
    takeover_validate,
)

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
)


def run_program_pipeline(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_factory: Callable[[str, config.Paths, str, str, str], ToolRun],
    max_targets_per_step: int | None = None,
) -> PipelineResult:
    """Run every active runner once for `(platform, slug)` sequentially.

    `tool_factory(runner_name, paths, platform, slug, run_id)` builds the
    `tool_run` callable for each runner — the CLI passes the real
    factory that wires subprocess + watchdog; tests pass a fake.
    """
    abort = _gate_check(paths, platform, slug)
    if abort is not None:
        return PipelineResult(
            platform=platform, slug=slug, steps=(), aborted_reason=abort,
        )

    steps: list[StepResult] = []
    for name, run_program in _PIPELINE:
        run_id = uuid.uuid4().hex
        try:
            tool_run = tool_factory(name, paths, platform, slug, run_id)
            result = run_program(
                paths, platform, slug,
                tool_run=tool_run, run_id=run_id,
                max_targets=max_targets_per_step,
            )
        except (flags.ReconDisabled, flags.ProgramFrozen) as exc:
            # Kill switch flipped mid-pipeline — short-circuit hard.
            return PipelineResult(
                platform=platform, slug=slug, steps=tuple(steps),
                aborted_reason=f"{type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            steps.append(StepResult(
                runner=name, status="failed",
                detail=f"{type(exc).__name__}: {exc}",
            ))
            continue
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
