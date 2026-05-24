"""Single-turn execution logic for MissionController."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .actions.matrix import PhaseViolationError, check_phase_action
from .actions.schemas import ActionEnvelope, InvalidActionError, parse_action
from .controller_dispatch import dispatch
from .llm.prompts import format_observation_message
from .models import TurnStatus, ValidationStatus
from .persistence import (
    create_turn, finish_turn, record_action,
)

if TYPE_CHECKING:
    from .controller import MissionController

logger = logging.getLogger(__name__)

_MAX_SCHEMA_RETRIES = 2


async def _call_llm_with_retries(ctrl, turn):
    """Call LLM and retry up to _MAX_SCHEMA_RETRIES times on schema errors."""
    for attempt in range(_MAX_SCHEMA_RETRIES + 1):
        llm_resp = await ctrl.provider.complete(ctrl.system_prompt, ctrl.messages)
        turn.input_tokens += llm_resp.input_tokens
        turn.output_tokens += llm_resp.output_tokens
        turn.save(update_fields=["input_tokens", "output_tokens"])

        try:
            raw = json.loads(llm_resp.raw_text)
            return parse_action(raw), llm_resp
        except (json.JSONDecodeError, InvalidActionError) as exc:
            if attempt < _MAX_SCHEMA_RETRIES:
                logger.warning(
                    "LLM schema retry %d/%d: %s | raw: %.200s",
                    attempt + 1, _MAX_SCHEMA_RETRIES,
                    exc, llm_resp.raw_text,
                )
                correction = _build_correction_message(str(exc), llm_resp.raw_text)
                ctrl.messages.append(
                    {"role": "assistant", "content": llm_resp.raw_text[:500]},
                )
                ctrl.messages.append({"role": "user", "content": correction})
                continue
            return exc, llm_resp
    return None, None  # pragma: no cover


def _build_correction_message(error_msg: str, raw_text: str) -> str:
    """Build a specific correction prompt telling the LLM exactly what's wrong."""
    parts = [f"Your response was invalid JSON: {error_msg}"]
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and not parsed:
            parts.append("You returned an empty object {}.")
        elif isinstance(parsed, dict) and "action" in parsed:
            parts.append(f"Action '{parsed['action']}' is missing required fields.")
    except (json.JSONDecodeError, AttributeError):
        parts.append("Your response was not valid JSON.")
    parts.append(
        "Required envelope: {\"action\": \"...\", \"goal\": \"...\", "
        "\"reason\": \"...\", \"hypothesis\": \"...\", ...action-specific fields}. "
        "Respond with a single raw JSON object. No markdown, no code fences."
    )
    return format_observation_message(denial_reason=" ".join(parts))


async def run_turn(ctrl: MissionController) -> bool:
    """Execute one turn. Return True if the mission should stop."""
    turn = create_turn(ctrl.session, model=ctrl.model_name)
    turn.input_tokens = 0
    turn.output_tokens = 0
    ctrl.budget.consume("turns")

    try:
        result, llm_resp = await _call_llm_with_retries(ctrl, turn)

        if isinstance(result, Exception):
            return _handle_invalid(ctrl, turn, str(result), llm_resp.raw_text)

        envelope = result
        try:
            check_phase_action(ctrl.session.current_phase, envelope.action)
        except PhaseViolationError as exc:
            return _handle_denied(ctrl, turn, envelope, str(exc))

        return await dispatch(ctrl, turn, envelope)
    finally:
        ctrl.session.consumed_budget = ctrl.budget.consumed_snapshot()
        ctrl.session.save(update_fields=["consumed_budget"])


def _handle_invalid(ctrl, turn, error_msg: str, raw_text: str) -> bool:
    action_type = "unknown"
    try:
        action_type = json.loads(raw_text).get("action", "unknown")
    except (json.JSONDecodeError, AttributeError):
        pass

    record_action(
        turn=turn, action_type=action_type,
        args_redacted={"raw_excerpt": raw_text[:200]},
        validation_status=ValidationStatus.INVALID_SCHEMA,
    )
    finish_turn(turn, TurnStatus.ACTION_DENIED)
    ctrl.plateau.record_invalid()

    denial = format_observation_message(denial_reason=f"Invalid action: {error_msg}")
    ctrl.messages.append({"role": "assistant", "content": raw_text[:500]})
    ctrl.messages.append({"role": "user", "content": denial})
    return False


def _handle_denied(ctrl, turn, envelope: ActionEnvelope, reason: str) -> bool:
    record_action(
        turn=turn, action_type=envelope.action, args_redacted={},
        goal=envelope.goal, reason=envelope.reason,
        hypothesis=envelope.hypothesis,
        validation_status=ValidationStatus.DENIED_PHASE,
    )
    finish_turn(turn, TurnStatus.ACTION_DENIED)
    ctrl.plateau.record_denial()

    from .event_log import build_budget_snapshot, emit_action_denied
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    emit_action_denied(
        ctrl.session, turn.index, envelope.action, reason,
        goal=envelope.goal, hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
    )

    denial = format_observation_message(denial_reason=reason)
    raw = json.dumps({"action": envelope.action})
    ctrl.messages.append({"role": "assistant", "content": raw})
    ctrl.messages.append({"role": "user", "content": denial})
    return False
