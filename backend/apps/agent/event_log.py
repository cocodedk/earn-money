from __future__ import annotations

from apps.events.models import Event
from apps.events.types import EventType

from .models import AgentSession


def emit_session_started(session: AgentSession) -> Event:
    """Emit an event when an agent session starts."""
    return Event.log(
        type=EventType.AGENT_SESSION_STARTED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Agent session started: {session.mission_profile}",
        data={
            "session_id": str(session.pk),
            "mission_profile": session.mission_profile,
            "autonomy_mode": session.autonomy_mode,
            "current_phase": session.current_phase,
        },
    )


def emit_action_executed(
    session: AgentSession,
    turn_index: int,
    action_type: str,
) -> Event:
    """Emit an event when an agent action is executed."""
    return Event.log(
        type=EventType.AGENT_ACTION_EXECUTED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Action executed: {action_type} (turn {turn_index})",
        data={
            "session_id": str(session.pk),
            "turn_index": turn_index,
            "action_type": action_type,
        },
    )


def emit_action_denied(
    session: AgentSession,
    turn_index: int,
    action_type: str,
    reason: str,
) -> Event:
    """Emit an event when an agent action is denied."""
    return Event.log(
        type=EventType.AGENT_ACTION_DENIED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Action denied: {action_type} (turn {turn_index}): {reason}",
        data={
            "session_id": str(session.pk),
            "turn_index": turn_index,
            "action_type": action_type,
            "reason": reason,
        },
    )


def emit_phase_changed(
    session: AgentSession,
    from_phase: str,
    to_phase: str,
    reason: str,
) -> Event:
    """Emit an event when the agent transitions between phases."""
    return Event.log(
        type=EventType.AGENT_PHASE_CHANGED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Phase changed: {from_phase} → {to_phase}",
        data={
            "session_id": str(session.pk),
            "from_phase": from_phase,
            "to_phase": to_phase,
            "reason": reason,
        },
    )


def emit_note_created(
    session: AgentSession,
    note_type: str,
    turn_index: int,
) -> Event:
    """Emit an event when the agent creates a note."""
    return Event.log(
        type=EventType.AGENT_NOTE_CREATED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Note created: {note_type} (turn {turn_index})",
        data={
            "session_id": str(session.pk),
            "note_type": note_type,
            "turn_index": turn_index,
        },
    )


def emit_mission_finished(
    session: AgentSession,
    status: str,
    reason: str,
) -> Event:
    """Emit an event when the agent mission concludes."""
    return Event.log(
        type=EventType.AGENT_MISSION_FINISHED,
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Mission finished: {status}",
        data={
            "session_id": str(session.pk),
            "status": status,
            "reason": reason,
            "mission_profile": session.mission_profile,
        },
    )


def build_budget_snapshot(session: AgentSession, consumed: dict) -> dict:
    """Return a compact budget snapshot for embedding in event data."""
    return {
        "phase": session.current_phase,
        "consumed": consumed,
        "mission_budget": session.mission_budget,
    }


def summarize_observation(obs_dict: dict) -> dict:
    """Return a compact summary of a Playwright observation dict."""
    obs_dict = obs_dict if isinstance(obs_dict, dict) else {}
    discovered = obs_dict.get("discovered") or {}
    elements = obs_dict.get("elements") or {}
    if not isinstance(discovered, dict):
        discovered = {}
    if not isinstance(elements, dict):
        elements = {}

    def _list(value) -> list:
        return value if isinstance(value, list) else []

    return {
        "url": obs_dict.get("url", ""),
        "title": obs_dict.get("title", ""),
        "route_count": len(_list(discovered.get("routes"))),
        "asset_count": len(_list(discovered.get("assets"))),
        "element_count": (
            len(_list(elements.get("links")))
            + len(_list(elements.get("buttons")))
            + len(_list(elements.get("forms")))
        ),
        "network_count": len(_list(obs_dict.get("network"))),
    }
