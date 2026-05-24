"""Action dispatch and event emission for executed turns."""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from .actions.schemas import (
    ClickAction, FillFormAction, HttpRequestAction, NavigateAction,
    RequestPhaseTransitionAction, StopAction, StoreNoteAction,
    SubmitCandidateAction, SubmitFormAction,
)
from .llm.prompts import format_observation_message
from .models import ExecutionStatus, NoteType, ObservationType, TurnStatus
from .persistence import (
    finish_turn, record_action, record_note, record_observation,
)

if TYPE_CHECKING:
    from .actions.schemas import ActionEnvelope
    from .controller import MissionController


def _mark_executed(action_rec) -> None:
    action_rec.execution_status = ExecutionStatus.EXECUTED
    action_rec.save(update_fields=["execution_status"])


async def dispatch(ctrl: MissionController, turn, envelope: ActionEnvelope) -> bool:
    """Execute a validated action. Return True if the mission should stop."""
    args_redacted = {}
    if isinstance(envelope.parsed, SubmitCandidateAction):
        args_redacted = {
            "category": envelope.parsed.category,
            "description": envelope.parsed.description[:200],
            "evidence_refs": list(envelope.parsed.evidence_refs)[:20],
        }
    action_rec = record_action(
        turn=turn, action_type=envelope.action, args_redacted=args_redacted,
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

    if isinstance(parsed, SubmitCandidateAction):
        return _handle_submit_candidate(ctrl, turn, action_rec, envelope, parsed)

    if isinstance(parsed, ClickAction):
        await ctrl.driver.click(parsed.element_id)
        obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
        ctrl.budget.consume("browser_actions")
        _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
        return False

    if isinstance(parsed, FillFormAction):
        await ctrl.driver.fill(parsed.element_id, parsed.value)
        obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
        ctrl.budget.consume("form_fills")
        _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
        return False

    if isinstance(parsed, SubmitFormAction):
        await ctrl.driver.click(parsed.element_id)
        obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
        ctrl.budget.consume("form_submits")
        _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
        return False

    if isinstance(parsed, HttpRequestAction):
        http_obs = await ctrl.driver.http_request(parsed.method, parsed.path)
        record_observation(
            action=action_rec,
            observation_type=ObservationType.HTTP,
            data=http_obs,
        )
        _mark_executed(action_rec)
        ctrl.budget.consume("http_requests")
        _emit_and_finish(ctrl, turn, envelope, http_obs)
        return False

    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
    return False


def _handle_submit_candidate(
    ctrl,
    turn,
    action_rec,
    envelope: ActionEnvelope,
    parsed: SubmitCandidateAction,
) -> bool:
    fingerprint = _candidate_fingerprint(parsed)
    duplicate = _find_duplicate_candidate(ctrl.session, fingerprint)
    if duplicate is not None:
        reason = (
            "Duplicate candidate already submitted. Do not submit it again; "
            "stop if reporting is complete or continue only with new evidence."
        )
        _deny_duplicate_candidate(ctrl, turn, action_rec, envelope, reason)
        return False

    content = {
        "category": parsed.category,
        "description": parsed.description,
        "fingerprint": fingerprint,
    }
    record_note(
        ctrl.session,
        turn,
        NoteType.CANDIDATE,
        content,
        evidence_refs=parsed.evidence_refs,
    )
    from .event_log import emit_note_created
    emit_note_created(ctrl.session, NoteType.CANDIDATE, turn.index)

    action_rec.args_redacted = {
        "category": parsed.category,
        "description": parsed.description[:200],
        "evidence_refs": list(parsed.evidence_refs)[:20],
        "fingerprint": fingerprint,
    }
    action_rec.save(update_fields=["args_redacted"])
    _mark_executed(action_rec)
    ctrl.plateau.record_candidate()

    obs_dict = {
        "action": "submit_candidate",
        "status": "accepted",
        "candidate": {
            "category": parsed.category,
            "description": parsed.description,
            "evidence_refs": parsed.evidence_refs,
            "fingerprint": fingerprint,
        },
        "guidance": (
            "Candidate recorded. Do not submit the same candidate again; "
            "stop if reporting is complete or continue only with new evidence."
        ),
    }
    _emit_and_finish(ctrl, turn, envelope, obs_dict)
    return False


def _candidate_fingerprint(parsed: SubmitCandidateAction) -> str:
    return _candidate_fingerprint_from_values(
        parsed.category,
        parsed.description,
        parsed.evidence_refs,
    )


def _candidate_fingerprint_from_values(
    category: object,
    description: object,
    evidence_refs: object,
) -> str:
    refs = evidence_refs if isinstance(evidence_refs, list) else []
    payload = {
        "category": _normalize_candidate_text(category),
        "description": _normalize_candidate_text(description),
        "evidence_refs": sorted({
            _normalize_candidate_text(ref) for ref in refs if ref is not None
        }),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_candidate_text(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _find_duplicate_candidate(session, fingerprint: str):
    notes = (
        session.notes
        .filter(note_type=NoteType.CANDIDATE)
        .order_by("pk")
        .only("pk", "content", "evidence_refs")
    )
    for note in notes:
        content = note.content if isinstance(note.content, dict) else {}
        note_fingerprint = content.get("fingerprint") or _candidate_fingerprint_from_values(
            content.get("category", ""),
            content.get("description", ""),
            note.evidence_refs,
        )
        if note_fingerprint == fingerprint:
            return note
    return None


def _deny_duplicate_candidate(ctrl, turn, action_rec, envelope, reason: str) -> None:
    action_rec.execution_status = ExecutionStatus.SKIPPED
    action_rec.denial_reason = reason
    action_rec.save(update_fields=["execution_status", "denial_reason"])
    finish_turn(turn, TurnStatus.ACTION_DENIED)
    ctrl.plateau.record_denial()

    from .event_log import build_budget_snapshot, emit_action_denied
    snapshot = build_budget_snapshot(ctrl.session, ctrl.budget.consumed_snapshot())
    emit_action_denied(
        ctrl.session,
        turn.index,
        envelope.action,
        reason,
        goal=envelope.goal,
        hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
    )

    raw = json.dumps({"action": envelope.action})
    ctrl.messages.append({"role": "assistant", "content": raw})
    ctrl.messages.append({
        "role": "user",
        "content": format_observation_message(denial_reason=reason),
    })


def _handle_phase_transition(ctrl, parsed) -> None:
    from .phases import is_valid_transition

    if not is_valid_transition(parsed.from_phase, parsed.to_phase):
        return

    if parsed.to_phase == "verify" and not _has_candidate(ctrl.session):
        from .llm.prompts import format_observation_message
        denial = format_observation_message(
            denial_reason="Cannot transition to verify: no valid "
            "submit_candidate action exists yet. Submit a candidate first.",
        )
        raw = json.dumps({"action": parsed.__class__.__name__})
        ctrl.messages.append({"role": "assistant", "content": raw})
        ctrl.messages.append({"role": "user", "content": denial})
        return

    from .event_log import build_budget_snapshot, emit_phase_changed
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    emit_phase_changed(
        ctrl.session, parsed.from_phase, parsed.to_phase, parsed.reason,
        budget_snapshot=snapshot,
    )
    ctrl.advance_phase(parsed.to_phase, parsed.reason)


def _has_candidate(session) -> bool:
    """Return True if the session has at least one valid submit_candidate action."""
    from .models import AgentAction, ValidationStatus
    return AgentAction.objects.filter(
        turn__session=session,
        action_type="submit_candidate",
        validation_status=ValidationStatus.VALID,
    ).exists()


def _emit_and_finish_browser(ctrl, turn, envelope, obs_dict: dict) -> None:
    from .event_log import (
        build_budget_snapshot, emit_action_executed, summarize_observation,
    )
    snapshot = build_budget_snapshot(ctrl.session, ctrl.budget.consumed_snapshot())
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


def _emit_and_finish(ctrl, turn, envelope, obs_dict: dict) -> None:
    from .event_log import build_budget_snapshot, emit_action_executed
    snapshot = build_budget_snapshot(ctrl.session, ctrl.budget.consumed_snapshot())
    emit_action_executed(
        ctrl.session, turn.index, envelope.action,
        goal=envelope.goal, reason=envelope.reason,
        hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
        observation_summary=obs_dict,
    )
    finish_turn(turn, TurnStatus.COMPLETED)
    obs_msg = format_observation_message(obs_dict=obs_dict)
    raw = json.dumps({"action": envelope.action})
    ctrl.messages.append({"role": "assistant", "content": raw})
    ctrl.messages.append({"role": "user", "content": obs_msg})


async def _execute_browser_action(ctrl, turn, action_rec, envelope):
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
    route_paths = [r.path for r in obs.discovered.routes]
    new_elements = (
        len(obs.elements.links) + len(obs.elements.buttons)
        + len(obs.elements.inputs) + len(obs.elements.forms)
    )
    ctrl.plateau.record_turn(new_routes=new_routes, new_elements=new_elements, route_paths=route_paths)
    return obs_dict
