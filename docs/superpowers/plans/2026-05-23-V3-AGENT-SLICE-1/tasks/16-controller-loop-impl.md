# Task 16 — Controller: init + run()

Part of [Task 16](16-controller-loop.md). Imports, `__init__`, and `run()` method.

```python
# backend/apps/agent/controller.py
from __future__ import annotations

import json
import hashlib
import logging
from typing import Any

from .actions.schemas import parse_action, InvalidActionError
from .actions.matrix import (
    check_phase_action, allowed_actions_for_phase, PhaseViolationError,
)
from .budgets import BudgetTracker, BudgetExhaustedError
from .plateau import PlateauDetector
from .observations.builder import ObservationBuilder
from .observations.assets import AssetObservation, AssetExcerpt
from .persistence import (
    create_session, create_turn, record_action, record_observation,
    record_note, finish_turn, finish_session,
)
from .event_log import (
    emit_session_started, emit_action_executed, emit_action_denied,
    emit_phase_changed, emit_note_created, emit_mission_finished,
)
from .llm.prompts import build_system_prompt, format_observation_message
from .llm.providers import LLMProvider
from .phases import is_valid_transition
from .models import (
    AgentSession, SessionStatus, TurnStatus,
    ValidationStatus, ExecutionStatus,
)

logger = logging.getLogger(__name__)

SLICE_1_PHASES = ["recon", "enumerate", "report"]


class MissionController:
    def __init__(
        self,
        provider: LLMProvider,
        driver: Any,
        scan_run: Any,
        target_run: Any,
        target: Any,
        mission_profile: str,
        mission_budget: dict[str, Any],
        phase_budgets: dict[str, dict[str, Any]],
        objective: str = "Find the hidden scoreboard page",
        model_name: str = "mock",
    ) -> None:
        self._provider = provider
        self._driver = driver
        self._scan_run = scan_run
        self._target_run = target_run
        self._target = target
        self._profile = mission_profile
        self._mission_budget = mission_budget
        self._phase_budgets = phase_budgets
        self._objective = objective
        self._model_name = model_name
        self._messages: list[dict[str, str]] = []
        self._session: AgentSession | None = None
        self._obs_builder: ObservationBuilder | None = None
        self._seen_routes: set[str] = set()
        self._seen_elements: set[str] = set()

    async def run(self) -> AgentSession:
        self._session = create_session(
            scan_run=self._scan_run,
            target_run=self._target_run,
            target=self._target,
            mission_profile=self._profile,
            model_policy={"primary_model": self._model_name},
            mission_budget=self._mission_budget,
        )
        emit_session_started(self._session)
        self._obs_builder = ObservationBuilder(
            target_origin=self._target.host,
        )
        phase_budget = self._phase_budgets.get("recon", {})
        budget = BudgetTracker(
            mission_budget=self._mission_budget,
            phase_budget=phase_budget,
        )
        plateau = PlateauDetector()

        stop_reason = "budget_exhausted"
        final_status = SessionStatus.STOPPED
        try:
            while True:
                budget.check_all()
                turn = create_turn(session=self._session, model=self._model_name)
                result = await self._run_turn(turn, budget, plateau)
                budget.consume("turns", 1)
                if result == "stop":
                    stop_reason = "objective_or_stop"
                    break
                if result.startswith("phase_transition:"):
                    _, requested, reason = result.split(":", 2)
                    current = self._session.current_phase
                    if (
                        requested in SLICE_1_PHASES
                        and is_valid_transition(current, requested)
                    ):
                        self._advance_phase(requested, current, reason, budget)
                        plateau = PlateauDetector()
                if plateau.is_plateaued():
                    current = self._session.current_phase
                    nxt = self._next_slice_phase(current)
                    if nxt:
                        self._advance_phase(nxt, current, plateau.plateau_reason(), budget)
                        plateau = PlateauDetector()
        except BudgetExhaustedError:
            stop_reason = "budget_exhausted"
        except Exception as exc:
            logger.exception("Agent mission failed")
            stop_reason = f"error:{exc.__class__.__name__}"
            final_status = SessionStatus.FAILED
        else:
            final_status = (
                SessionStatus.COMPLETED if stop_reason == "objective_or_stop"
                else SessionStatus.STOPPED
            )
        finish_session(self._session, final_status, budget.consumed_snapshot())
        emit_mission_finished(self._session, final_status, stop_reason)
        return self._session

    def _next_slice_phase(self, current: str) -> str | None:
        try:
            idx = SLICE_1_PHASES.index(current)
        except ValueError:
            return None
        if idx + 1 < len(SLICE_1_PHASES):
            return SLICE_1_PHASES[idx + 1]
        return None

    def _advance_phase(
        self, nxt: str, current: str, reason: str,
        budget: BudgetTracker,
    ) -> None:
        emit_phase_changed(self._session, current, nxt, reason)
        self._session.current_phase = nxt
        self._session.save(update_fields=["current_phase", "updated_at"])
        budget.switch_phase(self._phase_budgets.get(nxt, {}))
```

Continues in [16-controller-loop-turn.md](16-controller-loop-turn.md).
