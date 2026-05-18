"""No-op observation hooks for HackerLoop.

Extracted as a mixin so the main hacker_loop.py file stays under the
project's 200-line cap. Subclasses (ProbeRunner) override these to push
events to a queue / event history; the base class needs them to exist
so `run()` can call them unconditionally.
"""
from __future__ import annotations

from typing import Any

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_policy import PolicyDecision


class HackerLoopHooksMixin:
    """No-op default implementations. Override in subclasses."""

    def _on_llm_response(
        self, turn: int, raw: str | None, model_id: str | None,
        *, system: str, prompt: str, attempt: int, used_response_format: bool,
    ) -> None:
        """Called once per (turn, attempt) after the LLM call returns, BEFORE parsing.
        `raw` may be None when the provider raised."""

    def _on_action_parsed(
        self, turn: int, action: object, parse_recovered: bool, *, attempt: int,
    ) -> None:
        """Called after `parse_action_with_recovery` returns. `attempt`
        identifies which call's `raw` actually parsed."""

    def _on_action_parse_failed(self, turn: int, attempt: int, error: str) -> None:
        """Called from inside the `except ActionParseError` block in `run()`.
        Fires once per failed parse attempt."""

    def _on_policy_decision(self, turn: int, action: object, decision: PolicyDecision) -> None:
        """Called after `roe_policy.decide(action.category)`."""

    def _on_observation(self, turn: int, action: object, obs: ObservationWrapper) -> None:
        """Called after each successful http_tool.get/post."""

    def _on_finding(self, turn: int, kind: str, finding: dict[str, Any]) -> None:
        """Called per candidate and per verified."""

    def _on_turn_complete(self, turn: int, action: object, stage: str) -> None:
        """Called at end of iteration. stage is 'completed' or 'denied'."""
