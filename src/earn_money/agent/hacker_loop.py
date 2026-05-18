"""RoE-controlled LLM probe loop.

think → validate → act → observe → verify
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from earn_money.agent.action_classes import classify_action
from earn_money.agent.budget import BudgetExceeded, RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.probe_actions import (
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
)
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile
from earn_money.agent.scope_policy import ScopeDenied
from earn_money.agent.task_router import TaskType

from ._hacker_loop_hooks import HackerLoopHooksMixin
from ._hacker_loop_turn import handle_stop, parse_or_retry
from .hacker_loop_executor import execute_action
from .hacker_loop_prompt import _SYSTEM_PROMPT, build_prompt
from .hacker_loop_provider import _call_provider_with_rf_fallback

log = logging.getLogger(__name__)

# Re-export so existing importers
# (`from earn_money.agent.hacker_loop import _SYSTEM_PROMPT,
# _call_provider_with_rf_fallback`) keep working after the split.
__all__ = [
    "_SYSTEM_PROMPT",
    "HackerLoop",
    "LoopResult",
    "_call_provider_with_rf_fallback",
]


@dataclass
class LoopResult:
    turns: int
    candidate_findings: list[dict[str, Any]]
    verified_findings: list[dict[str, Any]]
    policy_denials: list[str]
    stop_reason: str


class HackerLoop(HackerLoopHooksMixin):
    def __init__(
        self,
        profile: RoeProfile,
        roe_policy: RoePolicy,
        http_tool: HttpTool,
        budget: RequestBudget,
        session: HackerSession,
        verifier: FindingVerifier,
        provider: Any,  # earn_money.agent.providers.Provider
    ) -> None:
        self.profile = profile
        self.roe_policy = roe_policy
        self.http_tool = http_tool
        self.budget = budget
        self.session = session
        self.verifier = verifier
        self.provider = provider
        self._current_turn: int = 0
        self._last_model_id: str | None = None
        self._consecutive_stop_rejections: int = 0
        self._last_stop_rejection_reason: str | None = None

    # Observation hooks live on HackerLoopHooksMixin (no-op defaults).

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self) -> LoopResult:
        turn = 0
        consecutive_denials = 0

        while turn < self.budget.max_turns:
            turn += 1
            self._current_turn = turn
            try:
                self.budget.check_turn(turn)
            except BudgetExceeded as e:
                return self._result(turn, f"budget_exceeded: {e}")

            prompt = self._build_prompt()
            raw, used_rf = self._get_llm_response(prompt)
            self._on_llm_response(
                turn, raw, self._last_model_id,
                system=_SYSTEM_PROMPT, prompt=prompt,
                attempt=1, used_response_format=used_rf,
            )
            if raw is None:
                return self._result(turn, "llm_error")

            action, parse_recovered, attempt, terminal = parse_or_retry(
                self, turn, raw, used_rf, prompt,
            )
            if terminal is not None:
                return terminal
            assert action is not None  # parse_or_retry invariant when terminal is None
            self._on_action_parsed(turn, action, parse_recovered, attempt=attempt)

            if isinstance(action, StopAction):
                disposition, stop_result = handle_stop(self, turn, action)
                if disposition == "rejected_continue":
                    continue
                assert stop_result is not None
                return stop_result

            # Any non-stop action resets the rejection counter + clears the
            # surfaced rejection note (the model has moved on).
            self._consecutive_stop_rejections = 0
            self._last_stop_rejection_reason = None

            decision = self.roe_policy.decide(action.category)
            self._on_policy_decision(turn, action, decision)
            if not decision.allowed:
                self.session.add_policy_denial(decision.reason)
                self.session.log_turn(action.model_dump(), f"denied: {decision.reason}")
                consecutive_denials += 1
                self._on_turn_complete(turn, action, "denied")
                if consecutive_denials >= 3:
                    return self._result(turn, "repeated_denials")
                continue
            consecutive_denials = 0

            try:
                self._execute_action(action)
            except BudgetExceeded as e:
                return self._result(turn, f"budget_exceeded: {e}")
            except ScopeDenied as e:
                return self._result(turn, f"scope_denied: {e}")

            self.session.record_action_class(classify_action(action))
            self.session.log_turn(action.model_dump(), "completed")
            self._on_turn_complete(turn, action, "completed")

        return self._result(turn, "max_turns")

    def _execute_action(
        self,
        action: GetAction | PostAction | SetHeaderAction | StoreAction | ReportCandidateAction,
    ) -> None:
        execute_action(self, action)

    def _build_prompt(self) -> str:
        return build_prompt(
            self.profile, self.session,
            last_stop_rejection_reason=self._last_stop_rejection_reason,
        )

    def _get_llm_response(
        self, prompt: str, *, with_response_format: bool = True,
    ) -> tuple[str | None, bool]:
        return _call_provider_with_rf_fallback(
            self.provider, system=_SYSTEM_PROMPT, user=prompt,
            task=TaskType.AGENT_PLANNING,
            with_response_format=with_response_format,
        )

    def _result(self, turn: int, stop_reason: str) -> LoopResult:
        return LoopResult(
            turns=turn,
            candidate_findings=list(self.session.candidate_findings),
            verified_findings=list(self.session.verified_findings),
            policy_denials=list(self.session.policy_denials),
            stop_reason=stop_reason,
        )
