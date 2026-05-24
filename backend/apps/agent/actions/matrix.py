from __future__ import annotations

_RECON_ACTIONS = {
    "observe_page",
    "navigate",
    "inspect_asset",
    "store_note",
    "request_phase_transition",
    "stop",
}

_ENUMERATE_ACTIONS = _RECON_ACTIONS | {
    "click",
    "fill_form",
    "submit_candidate",
}

_PROBE_ACTIONS = _ENUMERATE_ACTIONS | {
    "submit_form",
    "http_request",
    "run_stub",
    "run_tool",
    "request_verify",
}

_VERIFY_ACTIONS = _PROBE_ACTIONS | {
    "diff_response",
    "compare_baseline",
}

_REPORT_ACTIONS = {
    "store_note",
    "submit_candidate",
    "stop",
}

_PHASE_ACTION_MATRIX: dict[str, set[str]] = {
    "recon": _RECON_ACTIONS,
    "enumerate": _ENUMERATE_ACTIONS,
    "probe": _PROBE_ACTIONS,
    "verify": _VERIFY_ACTIONS,
    "report": _REPORT_ACTIONS,
}


class PhaseViolationError(ValueError):
    """Raised when an action is not permitted in the current phase."""


def check_phase_action(phase: str, action: str) -> None:
    """Raise PhaseViolationError if action is not allowed in phase."""
    allowed = _PHASE_ACTION_MATRIX.get(phase)
    if allowed is None:
        raise PhaseViolationError(f"Unknown phase {phase!r}")
    if action not in allowed:
        raise PhaseViolationError(
            f"Action {action!r} is not permitted in phase {phase!r}. "
            f"Allowed: {sorted(allowed)}"
        )


def allowed_actions_for_phase(phase: str) -> list[str]:
    """Return sorted list of actions allowed in phase."""
    allowed = _PHASE_ACTION_MATRIX.get(phase)
    if allowed is None:
        raise PhaseViolationError(f"Unknown phase {phase!r}")
    return sorted(allowed)
