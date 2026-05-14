"""Anthropic-API-backed decision layer for the active-recon pipeline.

The agent reads a snapshot of program state (recent runs, signals,
findings, RoE) and decides the next pipeline step, optionally
surfacing proposals for new tools or scripts that current runners
can't cover.

Hard boundaries — enforced by the orchestrator, NOT trusted from
the agent's reply:

- Cannot bypass `scope.md`, `roe.md`, `RECON_ENABLED`, or `FROZEN`.
- Cannot promote findings (`_queue → _verified → _submitted`).
- Cannot execute proposed scripts — they land in `scratch/agent-proposals/`
  with the executable bit OFF for operator review.
"""

from earn_money.agent.decider import (
    AgentDecider,
    Decision,
    Proposal,
    decide_next_step,
)
from earn_money.agent.state import PipelineState, build_state

__all__ = [
    "AgentDecider",
    "Decision",
    "PipelineState",
    "Proposal",
    "build_state",
    "decide_next_step",
]
