"""Per-turn helpers for HackerLoop.run() — parse-with-retry and the
StopAction reject/accept gate.

Extracted from hacker_loop.py to keep the main loop body under the
project's 200-line file cap. Both helpers take `loop` (the HackerLoop
instance) explicitly; they read the prompt + LLM-response state on it
and return a sentinel signalling the outer loop to `continue` /
`return` / proceed with the parsed action.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from earn_money.agent.action_classes import untried_applicable_classes
from earn_money.agent.probe_actions import (
    ActionParseError,
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
    parse_action_with_recovery,
)

from .hacker_loop_prompt import _SYSTEM_PROMPT

if TYPE_CHECKING:
    from .hacker_loop import HackerLoop, LoopResult

log = logging.getLogger("earn_money.agent.hacker_loop")

_ParsedAction = (
    GetAction | PostAction | SetHeaderAction | StoreAction | ReportCandidateAction | StopAction
)


def parse_or_retry(
    loop: HackerLoop, turn: int, raw: str, used_rf: bool, prompt: str,
) -> tuple[_ParsedAction | None, bool, int, LoopResult | None]:
    """Try `parse_action_with_recovery`; on failure, retry without
    response_format if the first call used it. Returns
    `(action, parse_recovered, attempt, terminal_result)` — the
    terminal_result is non-None if the outer loop should return it."""
    try:
        action, parse_recovered = parse_action_with_recovery(raw)
        return action, parse_recovered, 1, None
    except ActionParseError as first_err:
        loop._on_action_parse_failed(turn, 1, str(first_err))
        # Skip the retry if response_format wasn't actually used
        # on the call that produced this garbage — same kwargs
        # would just return the same garbage.
        if not used_rf:
            log.warning("Invalid action from LLM: %s", first_err)
            return None, False, 1, loop._result(turn, "invalid_action")
        log.warning(
            "Parse failed with response_format; retrying without: %s",
            first_err,
        )
        raw2, used_rf2 = loop._get_llm_response(prompt, with_response_format=False)
        loop._on_llm_response(
            turn, raw2, loop._last_model_id,
            system=_SYSTEM_PROMPT, prompt=prompt,
            attempt=2, used_response_format=used_rf2,
        )
        if raw2 is None:
            return None, False, 2, loop._result(turn, "llm_error")
        try:
            action, parse_recovered = parse_action_with_recovery(raw2)
            return action, parse_recovered, 2, None
        except ActionParseError as second_err:
            loop._on_action_parse_failed(turn, 2, str(second_err))
            log.warning("Invalid action from LLM after retry: %s", second_err)
            return None, False, 2, loop._result(turn, "invalid_action")


def handle_stop(loop: HackerLoop, turn: int, action: StopAction) -> tuple[str, LoopResult | None]:
    """Decide whether the model's StopAction is accepted or rejected.

    Returns `(disposition, terminal_result)`:
      - disposition == "accepted" → terminal_result is the LoopResult
      - disposition == "rejected_continue" → outer loop should `continue`
      - disposition == "rejected_terminal" → terminal_result is policy_stop
    """
    applicable = untried_applicable_classes(
        loop.session, loop.profile, loop.session.tried_action_classes,
    )
    turns_remaining = loop.budget.max_turns - turn
    if applicable and turns_remaining > 0:
        loop._consecutive_stop_rejections += 1
        reason = (
            f"STOP rejected. {turns_remaining} turn(s) remain and "
            f"these applicable action classes are still untried: "
            f"{sorted(c.value for c in applicable)}. "
            f"Choose an action from the menu that exercises one of them."
        )
        loop._last_stop_rejection_reason = reason
        log.info("STOP rejected at turn %d: %s", turn, reason)
        loop.session.log_turn(action.model_dump(), f"stop_rejected: {reason}")
        loop._on_turn_complete(turn, action, "stop_rejected")
        if loop._consecutive_stop_rejections >= 2:
            return "rejected_terminal", loop._result(turn, "policy_stop")
        return "rejected_continue", None
    loop._on_turn_complete(turn, action, "completed")
    loop.session.log_turn(action.model_dump(), "stop")
    return "accepted", loop._result(turn, action.args.reason or "stop")
