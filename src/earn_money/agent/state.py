"""Build a JSON-serializable snapshot of a program's state for the agent.

Pure read against the program DB + filesystem. No mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from earn_money import config, flags, roe, scope
from earn_money.dashboard import aggregator_blocks
from earn_money.engine.active_pipeline import StepResult


@dataclass(frozen=True)
class PipelineState:
    """The agent's view of one program at a decision point."""
    platform: str
    slug: str
    policy: str
    frozen: bool
    frozen_reason: str | None
    scope_summary: dict[str, Any]
    roe_summary: dict[str, Any]
    finding_states: dict[str, int]
    recent_runs: list[dict[str, Any]]
    recent_signals: list[dict[str, Any]]
    active_runs: list[dict[str, Any]]
    completed_steps: list[dict[str, Any]]
    available_steps: list[str]

    def to_json(self) -> dict[str, Any]:
        """Render as a plain dict suitable for sending to the model."""
        return asdict(self)


def build_state(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    completed_steps: tuple[StepResult, ...] = (),
) -> PipelineState:
    """Assemble a state snapshot for `(platform, slug)`.

    `completed_steps` is the orchestrator's per-pipeline log so the agent
    can avoid re-suggesting work that just ran.
    """
    s = scope.read_scope(paths.scope_file(platform, slug))
    program_roe = roe.read_roe(paths.roe_file(platform, slug))
    block, _ = aggregator_blocks.db_block(paths, platform, slug)

    return PipelineState(
        platform=platform,
        slug=slug,
        policy=s.policy,
        frozen=paths.freeze_flag(platform, slug).exists(),
        frozen_reason=flags.freeze_reason_text(paths, platform, slug),
        scope_summary={
            "in_scope_count": len(s.in_scope),
            "out_of_scope_count": len(s.out_of_scope),
            "last_synced": s.last_synced,
        },
        roe_summary=program_roe.manifest_payload(),
        finding_states=block["finding_states"],
        recent_runs=block["recent_runs"],
        recent_signals=block["recent_signals"],
        active_runs=block["active_runs"],
        completed_steps=[
            {
                "runner": s.runner, "status": s.status,
                "outputs_recorded": s.outputs_recorded,
                "detail": s.detail,
            }
            for s in completed_steps
        ],
        available_steps=list(_AVAILABLE_STEPS),
    )


_AVAILABLE_STEPS: tuple[str, ...] = (
    "httpx-probe",
    "nuclei-scan",
    "takeover-validate",
    "sourcemap-scan",
    "katana-crawl",
    "graphql-probe",
    "stop",
)
