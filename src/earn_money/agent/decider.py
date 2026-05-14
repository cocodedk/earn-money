"""Single-shot agent decider — picks the next pipeline step.

Sends a state snapshot to the configured LLM provider, parses a
JSON-shaped reply, validates it against the hard boundaries (allowed
step set, numeric arg range, proposal-filename slug grammar), and
returns a validated Decision to the orchestrator.

If the reply doesn't parse or violates a rule, the decider falls
back to the next sequential step + flags the failure in
`Decision.reason` and `Decision.provider_error`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from earn_money import config
from earn_money.agent.decider_helpers import (
    ALLOWED_STEPS,
    SYSTEM_PROMPT,
    coerce_int,
    parse_reply,
    persist_proposals,
    render_user,
    safe_from_env,
)
from earn_money.agent.providers import Provider
from earn_money.agent.state import PipelineState, build_state
from earn_money.engine.active_pipeline import StepResult


@dataclass(frozen=True)
class Proposal:
    kind: str  # "script" | "tool_gap"
    slug: str
    body: str = ""
    language: str = "py"
    rationale: str = ""
    design: str = ""


@dataclass(frozen=True)
class Decision:
    next_step: str
    reason: str
    max_targets: int | None = None
    proposals: tuple[Proposal, ...] = field(default_factory=tuple)
    provider_error: str | None = None


class AgentDecider(Protocol):
    """Signature the active-pipeline orchestrator depends on."""

    def __call__(
        self,
        paths: config.Paths,
        platform: str,
        slug: str,
        *,
        completed_steps: tuple[StepResult, ...],
    ) -> Decision: ...


def decide_next_step(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    completed_steps: tuple[StepResult, ...] = (),
    provider: Provider | None = None,
    proposals_root: Path | None = None,
) -> Decision:
    """Build state → ask provider → validate reply → write proposals."""
    state = build_state(
        paths, platform, slug, completed_steps=completed_steps,
    )
    used_provider = provider or safe_from_env()
    if used_provider is None:
        return _fallback(state, "no provider configured")

    try:
        reply = used_provider.complete(system=SYSTEM_PROMPT, user=render_user(state))
    except Exception as exc:
        return _fallback(state, f"provider error: {type(exc).__name__}: {exc}")

    parsed = parse_reply(reply)
    if parsed is None:
        return _fallback(state, "could not parse provider reply as JSON")

    next_step = str(parsed.get("next_step") or "")
    if next_step not in ALLOWED_STEPS:
        return _fallback(
            state, f"provider chose unknown step {next_step!r}",
        )

    persisted = persist_proposals(
        parsed.get("proposals") or [],
        proposals_root=proposals_root or (paths.root / "scratch/agent-proposals"),
    )
    proposals = tuple(Proposal(**p) for p in persisted)
    return Decision(
        next_step=next_step,
        reason=str(parsed.get("reason") or "")[:500],
        max_targets=coerce_int(parsed.get("max_targets")),
        proposals=proposals,
    )


def _fallback(state: PipelineState, why: str) -> Decision:
    """Default to the next sequential step if the agent fails us."""
    completed = {s["runner"] for s in state.completed_steps}
    for step in state.available_steps:
        if step == "stop":
            continue
        if step not in completed:
            return Decision(
                next_step=step,
                reason=f"fallback (provider issue: {why})",
                provider_error=why,
            )
    return Decision(next_step="stop", reason="all steps done", provider_error=why)
