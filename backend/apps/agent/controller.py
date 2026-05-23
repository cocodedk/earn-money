"""MissionController — the core agent loop for V3 LLM-driven scanning."""
from __future__ import annotations

import logging

from .actions.matrix import allowed_actions_for_phase
from .budgets import BudgetExhaustedError, BudgetTracker
from .event_log import emit_mission_finished
from .llm.prompts import build_system_prompt
from .models import SessionStatus
from .observations.builder import ObservationBuilder
from .persistence import finish_session
from .phases import is_valid_transition
from .plateau import PlateauDetector

logger = logging.getLogger(__name__)

SLICE_1_PHASES = ["recon", "enumerate", "report"]


class MissionController:
    """Runs a mission: loop of LLM turns with budget/phase/plateau gates."""

    def __init__(
        self,
        session,
        provider,
        driver,
        objective: str,
        mission_budget: dict,
        phase_budgets: dict | None = None,
        model_name: str = "mock",
    ) -> None:
        self.session = session
        self.provider = provider
        self.driver = driver
        self.objective = objective
        self.model_name = model_name
        self._phase_budgets = phase_budgets or {}

        initial_phase_budget = self._phase_budgets.get(
            self.session.current_phase, {},
        )
        self.budget = BudgetTracker(mission_budget, initial_phase_budget)
        self.plateau = PlateauDetector()
        self.obs_builder = ObservationBuilder(
            target_origin=f"https://{session.target.host}",
        )
        self.messages: list[dict] = []

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        phase = self.session.current_phase
        return build_system_prompt(
            objective=self.objective,
            phase=phase,
            allowed_actions=allowed_actions_for_phase(phase),
            budget_remaining=self.budget.remaining("turns"),
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Execute turns until stop, budget exhaustion, or plateau."""
        from .controller_turn import run_turn

        try:
            while True:
                try:
                    self.budget.check("turns")
                except BudgetExhaustedError:
                    self._finish(SessionStatus.STOPPED, "budget_exhausted")
                    return

                should_stop = await run_turn(self)
                if should_stop:
                    self._finish(SessionStatus.COMPLETED, "stop_action")
                    return

                if self.plateau.is_plateaued():
                    advanced = self._try_auto_advance()
                    if not advanced:
                        reason = self.plateau.plateau_reason()
                        self._finish(SessionStatus.STOPPED, reason)
                        return
        except Exception:
            logger.exception("Mission loop error")
            self._finish(SessionStatus.FAILED, "unhandled_error")
            raise

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def advance_phase(self, to_phase: str, reason: str) -> None:
        """Transition to a new phase and reset phase budget."""
        self.session.current_phase = to_phase
        self.session.save(update_fields=["current_phase"])
        new_budget = self._phase_budgets.get(to_phase, {})
        self.budget.switch_phase(new_budget)
        self.plateau = PlateauDetector()

    def _try_auto_advance(self) -> bool:
        """Advance to next slice-1 phase on plateau. Return True if moved."""
        current = self.session.current_phase
        nxt = self._next_slice_phase(current)
        if nxt is None:
            return False
        if not is_valid_transition(current, nxt):
            return False  # pragma: no cover — defensive

        reason = f"auto-advance: {self.plateau.plateau_reason()}"
        from .event_log import emit_phase_changed
        emit_phase_changed(self.session, current, nxt, reason)
        self.advance_phase(nxt, reason)
        return True

    @staticmethod
    def _next_slice_phase(current: str) -> str | None:
        """Return the next phase in SLICE_1_PHASES, or None."""
        try:
            idx = SLICE_1_PHASES.index(current)
        except ValueError:
            return None
        nxt = idx + 1
        if nxt >= len(SLICE_1_PHASES):
            return None
        return SLICE_1_PHASES[nxt]

    # ------------------------------------------------------------------
    # Finish helper
    # ------------------------------------------------------------------

    def _finish(self, status: str, reason: str) -> None:
        consumed = self.budget.consumed_snapshot()
        finish_session(self.session, status, consumed)
        emit_mission_finished(self.session, status, reason)
