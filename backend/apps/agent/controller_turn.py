"""Single-turn execution logic for MissionController."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .actions.matrix import PhaseViolationError, check_phase_action
from .actions.schemas import ActionEnvelope, InvalidActionError, parse_action
from .llm.prompts import format_observation_message
from .models import ExecutionStatus, ObservationType, TurnStatus, ValidationStatus
from .persistence import (
    create_turn, finish_turn, record_action, record_note, record_observation,
)

if TYPE_CHECKING:
    from .controller import MissionController

logger = logging.getLogger(__name__)


def _mark_executed(action_rec) -> None:
    action_rec.execution_status = ExecutionStatus.EXECUTED
    action_rec.save(update_fields=["execution_status"])


async def run_turn(ctrl: MissionController) -> bool:
    """Execute one turn. Return True if the mission should stop."""
    turn = create_turn(ctrl.session, model=ctrl.model_name)
    ctrl.budget.consume("turns")

    try:
        llm_resp = await ctrl.provider.complete(ctrl.system_prompt, ctrl.messages)
        turn.input_tokens = llm_resp.input_tokens
        turn.output_tokens = llm_resp.output_tokens
        turn.save(update_fields=["input_tokens", "output_tokens"])

        raw: dict | str = {}
        try:
            raw = json.loads(llm_resp.raw_text)
            envelope = parse_action(raw)
        except (json.JSONDecodeError, InvalidActionError) as exc:
            return _handle_invalid(ctrl, turn, str(exc), llm_resp.raw_text)

        try:
            check_phase_action(ctrl.session.current_phase, envelope.action)
        except PhaseViolationError as exc:
            return _handle_denied(ctrl, turn, envelope, str(exc))

        return await _execute(ctrl, turn, envelope)
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


async def _execute(ctrl, turn, envelope: ActionEnvelope) -> bool:
    from .actions.schemas import (
        NavigateAction, RequestPhaseTransitionAction, StopAction, StoreNoteAction,
    )

    action_rec = record_action(
        turn=turn, action_type=envelope.action, args_redacted={},
        goal=envelope.goal, reason=envelope.reason, hypothesis=envelope.hypothesis,
    )
    parsed = envelope.parsed

    if isinstance(parsed, StopAction):
        _mark_executed(action_rec)
        finish_turn(turn, TurnStatus.COMPLETED)
        return True

    if isinstance(parsed, RequestPhaseTransitionAction):
        _handle_phase_transition(ctrl, parsed)
        _mark_executed(action_rec)
        finish_turn(turn, TurnStatus.COMPLETED)
        return False

    if isinstance(parsed, StoreNoteAction):
        record_note(ctrl.session, turn, parsed.note_type, parsed.content)
        from .event_log import emit_note_created
        emit_note_created(ctrl.session, parsed.note_type, turn.index)
        _mark_executed(action_rec)
        finish_turn(turn, TurnStatus.COMPLETED)
        ctrl.plateau.record_turn(new_routes=0, new_elements=0)
        return False

    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    from .event_log import (
        build_budget_snapshot, emit_action_executed, summarize_observation,
    )
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    obs_summary = summarize_observation(obs_dict)
    emit_action_executed(
        ctrl.session, turn.index, envelope.action,
        goal=envelope.goal, reason=envelope.reason,
        hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
        observation_summary=obs_summary,
    )
    finish_turn(turn, TurnStatus.COMPLETED)

    obs_msg = format_observation_message(obs_dict=obs_dict)
    raw = json.dumps({"action": envelope.action})
    ctrl.messages.append({"role": "assistant", "content": raw})
    ctrl.messages.append({"role": "user", "content": obs_msg})
    return False


def _handle_phase_transition(ctrl, parsed) -> None:
    from .phases import is_valid_transition

    if is_valid_transition(parsed.from_phase, parsed.to_phase):
        ctrl.advance_phase(parsed.to_phase, parsed.reason)
        from .event_log import emit_phase_changed
        emit_phase_changed(
            ctrl.session, parsed.from_phase, parsed.to_phase, parsed.reason,
        )


async def _execute_browser_action(ctrl, turn, action_rec, envelope):
    """Run observe_page / navigate / inspect_asset and return obs dict."""
    from .actions.schemas import NavigateAction

    if isinstance(envelope.parsed, NavigateAction):
        path = envelope.parsed.path or envelope.parsed.url_ref or "/"
        await ctrl.driver.navigate(path)

    net_entries = ctrl.driver.drain_network_log()
    obs = await ctrl.obs_builder.build_page_observation(
        page=ctrl.driver.page, turn=turn.index,
        phase=ctrl.session.current_phase,
        action_ref=str(action_rec.pk), network_entries=net_entries,
    )
    obs_dict = obs.to_dict()
    record_observation(
        action=action_rec, observation_type=ObservationType.PAGE, data=obs_dict,
    )
    _mark_executed(action_rec)

    new_routes = len(obs.discovered.routes)
    new_elements = len(obs.elements.links) + len(obs.elements.buttons)
    ctrl.plateau.record_turn(new_routes=new_routes, new_elements=new_elements)
    return obs_dict
