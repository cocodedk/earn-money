from __future__ import annotations

PHASE_ORDER: list[str] = ["recon", "enumerate", "probe", "verify", "report"]

_PHASE_INDEX: dict[str, int] = {phase: idx for idx, phase in enumerate(PHASE_ORDER)}


def next_phase(current: str) -> str | None:
    """Return the next phase after current, or None if current is the last phase."""
    idx = _PHASE_INDEX.get(current)
    if idx is None:
        return None
    next_idx = idx + 1
    if next_idx >= len(PHASE_ORDER):
        return None
    return PHASE_ORDER[next_idx]


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    """
    Return True if the transition is valid.

    Rules:
    - Any phase may transition to "report" (fast-path to reporting).
    - Forward-only transitions within the ordered sequence are allowed.
    - Backward transitions and same-phase transitions are rejected.
    - Transitions involving unknown phase names are rejected.
    """
    from_idx = _PHASE_INDEX.get(from_phase)
    to_idx = _PHASE_INDEX.get(to_phase)

    if from_idx is None or to_idx is None:
        return False

    if from_phase == to_phase:
        return False

    # Any phase can jump directly to report.
    if to_phase == "report":
        return True

    # Otherwise, only forward transitions are valid.
    return to_idx > from_idx
