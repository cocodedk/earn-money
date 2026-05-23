# Phase 8 — Controller, Phases & Mission Profiles

### Task 16: Controller loop

**Files:**
- Create: `backend/apps/agent/controller.py`
- Create: `backend/apps/agent/tests/test_controller.py`

The controller is the core mission loop. It orchestrates: LLM call → parse →
validate → execute → observe → persist → budget check → repeat.

- [ ] **Step 1: Write test for controller with mock LLM and browser**

```python
# backend/apps/agent/tests/test_controller.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import AgentSession, SessionStatus, AgentNote
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


@pytest.fixture
def scan_context():
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(host="juiceshop.cocode.dk", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return scan_run, target_run, target


def _mock_provider(responses: list[dict]) -> AsyncMock:
    provider = AsyncMock()
    call_count = 0

    async def complete(system_prompt, messages):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return LLMResponse(
            raw_text=json.dumps(responses[idx]),
            input_tokens=100, output_tokens=50, model="mock",
        )

    provider.complete = complete
    return provider


def _mock_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.page = AsyncMock()
    driver.page.url = "https://juiceshop.cocode.dk/"
    driver.page.title = AsyncMock(return_value="Juice Shop")
    driver.page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea", "name": "Juice Shop", "children": [],
    })
    driver.page.context.cookies = AsyncMock(return_value=[])
    driver.drain_network_log = MagicMock(return_value=[])
    driver.navigate = AsyncMock(return_value="https://juiceshop.cocode.dk/")
    driver.fetch_asset = AsyncMock(return_value=("content", 100, False))
    driver.is_in_scope = MagicMock(return_value=True)
    driver.start = AsyncMock()
    driver.stop = AsyncMock()
    return driver


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_stop_action_ends_mission(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See page", "args": {}},
        {"action": "stop", "goal": "Done", "args": {"reason": "nothing to do"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={"recon": {"max_turns": 6}, "enumerate": {"max_turns": 14}, "report": {"max_turns": 3}},
    )
    session = await controller.run()
    assert session.status == SessionStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_budget_exhaustion_stops(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See", "args": {}},
    ] * 5)
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 3},
        phase_budgets={"recon": {"max_turns": 3}, "enumerate": {"max_turns": 3}, "report": {"max_turns": 1}},
    )
    session = await controller.run()
    assert session.status == SessionStatus.STOPPED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_phase_transition(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See", "args": {}},
        {"action": "request_phase_transition", "goal": "Move on",
         "args": {"from_phase": "recon", "to_phase": "enumerate",
                  "reason": "Baseline done", "evidence_refs": []}},
        {"action": "stop", "goal": "Done", "args": {"reason": "finished"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={"recon": {"max_turns": 6}, "enumerate": {"max_turns": 14}, "report": {"max_turns": 3}},
    )
    session = await controller.run()
    assert session.current_phase == "report"
    assert session.status == SessionStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_denied_action_persisted(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "submit_candidate", "goal": "Report finding",
         "args": {"category": "xss", "description": "test", "evidence_refs": []}},
        {"action": "stop", "goal": "Done", "args": {"reason": "gave up"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={"recon": {"max_turns": 6}, "enumerate": {"max_turns": 14}, "report": {"max_turns": 3}},
    )
    session = await controller.run()
    from apps.agent.models import AgentAction, ValidationStatus
    denied = AgentAction.objects.filter(validation_status=ValidationStatus.DENIED_PHASE)
    assert denied.count() >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_controller.py -v`
Expected: FAIL

- [ ] **Step 3: Implement controller**

```python
# backend/apps/agent/controller.py
from __future__ import annotations

import json
import hashlib
import logging
from typing import Any

from .actions.schemas import parse_action, InvalidActionError
from .actions.matrix import check_phase_action, PhaseViolationError
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
from .models import (
    AgentSession, SessionStatus, TurnStatus,
    ValidationStatus, ExecutionStatus,
)

logger = logging.getLogger(__name__)

SLICE_1_ACTIONS = [
    "observe_page", "navigate", "inspect_asset",
    "store_note", "submit_candidate",
    "request_phase_transition", "stop",
]

PHASE_ORDER = ["recon", "enumerate", "report"]


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
        self._messages: list[dict[str, str]] = []
        self._session: AgentSession | None = None
        self._obs_builder: ObservationBuilder | None = None

    async def run(self) -> AgentSession:
        self._session = create_session(
            scan_run=self._scan_run,
            target_run=self._target_run,
            target=self._target,
            mission_profile=self._profile,
            model_policy={"primary_model": "mock"},
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
        try:
            while True:
                budget.check("turns")
                turn = create_turn(
                    session=self._session, model="mock",
                )
                result = await self._run_turn(turn, budget, plateau)
                budget.consume("turns", 1)
                if result == "stop":
                    stop_reason = "objective_or_stop"
                    break
                if result == "phase_transition":
                    current = self._session.current_phase
                    ci = PHASE_ORDER.index(current)
                    if ci + 1 < len(PHASE_ORDER):
                        next_phase = PHASE_ORDER[ci + 1]
                        emit_phase_changed(
                            self._session, current, next_phase,
                            "LLM requested transition",
                        )
                        self._session.current_phase = next_phase
                        self._session.save(update_fields=["current_phase", "updated_at"])
                        new_pb = self._phase_budgets.get(next_phase, {})
                        budget.switch_phase(new_pb)
                        plateau = PlateauDetector()
                if plateau.is_plateaued():
                    current = self._session.current_phase
                    ci = PHASE_ORDER.index(current)
                    if ci + 1 < len(PHASE_ORDER):
                        next_phase = PHASE_ORDER[ci + 1]
                        emit_phase_changed(
                            self._session, current, next_phase,
                            plateau.plateau_reason(),
                        )
                        self._session.current_phase = next_phase
                        self._session.save(update_fields=["current_phase", "updated_at"])
                        budget.switch_phase(self._phase_budgets.get(next_phase, {}))
                        plateau = PlateauDetector()
        except BudgetExhaustedError:
            stop_reason = "budget_exhausted"

        final_status = (
            SessionStatus.COMPLETED if stop_reason == "objective_or_stop"
            else SessionStatus.STOPPED
        )
        finish_session(self._session, final_status, budget.consumed_snapshot())
        emit_mission_finished(self._session, final_status, stop_reason)
        return self._session

    async def _run_turn(
        self, turn: Any, budget: BudgetTracker, plateau: PlateauDetector,
    ) -> str:
        system = build_system_prompt(
            objective=self._objective,
            phase=self._session.current_phase,
            allowed_actions=SLICE_1_ACTIONS,
            budget_remaining={
                "turns": budget.remaining("turns"),
            },
        )
        if not self._messages:
            self._messages.append({"role": "user", "content": "Begin your mission. Propose your first action."})

        resp = await self._provider.complete(system, self._messages)
        turn.prompt_hash = hashlib.sha256(system.encode()).hexdigest()[:16]
        turn.response_hash = hashlib.sha256(resp.raw_text.encode()).hexdigest()[:16]
        turn.input_tokens = resp.input_tokens
        turn.output_tokens = resp.output_tokens
        turn.prompt_artifact_ref = f"prompt_{turn.index}"
        turn.response_artifact_ref = f"response_{turn.index}"
        turn.status = TurnStatus.ACTION_PROPOSED
        turn.save(update_fields=[
            "prompt_hash", "response_hash", "input_tokens", "output_tokens",
            "prompt_artifact_ref", "response_artifact_ref", "status", "updated_at",
        ])

        try:
            raw = json.loads(resp.raw_text)
            envelope = parse_action(raw)
        except (json.JSONDecodeError, InvalidActionError) as e:
            action = record_action(
                turn=turn, action_type=raw.get("action", "unknown") if isinstance(raw, dict) else "unknown",
                args_redacted={}, goal="",
                validation_status=ValidationStatus.INVALID_SCHEMA,
            )
            action.denial_reason = str(e)
            action.execution_status = ExecutionStatus.SKIPPED
            action.save(update_fields=["denial_reason", "execution_status", "updated_at"])
            finish_turn(turn, TurnStatus.ACTION_DENIED)
            emit_action_denied(self._session, turn.index, "unknown", str(e))
            plateau.record_invalid()
            self._messages.append({"role": "assistant", "content": resp.raw_text})
            self._messages.append({"role": "user", "content": format_observation_message(None, denial_reason=str(e))})
            return "continue"

        try:
            check_phase_action(self._session.current_phase, envelope.action)
        except PhaseViolationError as e:
            action = record_action(
                turn=turn, action_type=envelope.action,
                args_redacted=raw.get("args", {}), goal=envelope.goal,
                validation_status=ValidationStatus.DENIED_PHASE,
            )
            action.denial_reason = str(e)
            action.execution_status = ExecutionStatus.SKIPPED
            action.save(update_fields=["denial_reason", "execution_status", "updated_at"])
            finish_turn(turn, TurnStatus.ACTION_DENIED)
            emit_action_denied(self._session, turn.index, envelope.action, str(e))
            plateau.record_denial()
            self._messages.append({"role": "assistant", "content": resp.raw_text})
            self._messages.append({"role": "user", "content": format_observation_message(None, denial_reason=str(e))})
            return "continue"

        action = record_action(
            turn=turn, action_type=envelope.action,
            args_redacted=raw.get("args", {}),
            goal=envelope.goal, reason=envelope.reason,
            hypothesis=envelope.hypothesis,
            validation_status=ValidationStatus.VALID,
        )

        obs_dict = await self._execute_action(envelope, action, turn)

        finish_turn(turn, TurnStatus.COMPLETED)
        emit_action_executed(self._session, turn.index, envelope.action)

        self._messages.append({"role": "assistant", "content": resp.raw_text})
        if obs_dict:
            self._messages.append({"role": "user", "content": format_observation_message(obs_dict)})
        plateau.record_turn(new_routes=0, new_elements=0)

        if envelope.action == "stop":
            return "stop"
        if envelope.action == "request_phase_transition":
            return "phase_transition"
        return "continue"

    async def _execute_action(
        self, envelope: Any, action: Any, turn: Any,
    ) -> dict[str, Any] | None:
        from django.utils import timezone
        action.execution_status = ExecutionStatus.EXECUTED
        action.executed_at = timezone.now()
        action.save(update_fields=["execution_status", "executed_at", "updated_at"])

        if envelope.action == "observe_page":
            network = self._driver.drain_network_log()
            obs = await self._obs_builder.build_page_observation(
                page=self._driver.page, turn=turn.index,
                phase=self._session.current_phase,
                action_ref=f"act_{turn.index}",
                network_entries=network,
            )
            obs_dict = obs.to_dict()
            record_observation(
                action=action, observation_type="page",
                data=obs_dict,
                content_hash=hashlib.sha256(json.dumps(obs_dict).encode()).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "navigate":
            path = envelope.parsed.path or ""
            await self._driver.navigate(path)
            network = self._driver.drain_network_log()
            obs = await self._obs_builder.build_page_observation(
                page=self._driver.page, turn=turn.index,
                phase=self._session.current_phase,
                action_ref=f"act_{turn.index}",
                network_entries=network,
            )
            obs_dict = obs.to_dict()
            record_observation(
                action=action, observation_type="page",
                data=obs_dict,
                content_hash=hashlib.sha256(json.dumps(obs_dict).encode()).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "inspect_asset":
            content, size, truncated = await self._driver.fetch_asset(
                envelope.parsed.asset_ref,
            )
            asset_obs = AssetObservation(
                asset_ref=envelope.parsed.asset_ref,
                path=envelope.parsed.asset_ref,
                type="script", size_bytes=size, truncated=truncated,
                excerpts=[], strings_of_interest=[],
            )
            obs_dict = asset_obs.to_dict()
            record_observation(
                action=action, observation_type="asset",
                data=obs_dict,
                content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "store_note":
            record_note(
                session=self._session, turn=turn,
                note_type=envelope.parsed.note_type,
                content=envelope.parsed.content,
            )
            emit_note_created(self._session, envelope.parsed.note_type, turn.index)
            return None

        if envelope.action == "submit_candidate":
            record_note(
                session=self._session, turn=turn,
                note_type="candidate",
                content={
                    "category": envelope.parsed.category,
                    "description": envelope.parsed.description,
                },
                evidence_refs=envelope.parsed.evidence_refs,
            )
            emit_note_created(self._session, "candidate", turn.index)
            return None

        return None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): add MissionController with phase/budget/plateau loop"
```

### Task 17: Phase transition logic

**Files:**
- Create: `backend/apps/agent/phases.py`
- Create: `backend/apps/agent/tests/test_phases.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_phases.py
from apps.agent.phases import next_phase, is_valid_transition, PHASE_ORDER


def test_phase_order():
    assert PHASE_ORDER == ["recon", "enumerate", "probe", "verify", "report"]


def test_next_phase_from_recon():
    assert next_phase("recon") == "enumerate"


def test_next_phase_from_report_is_none():
    assert next_phase("report") is None


def test_valid_forward_transition():
    assert is_valid_transition("recon", "enumerate")


def test_invalid_backward_transition():
    assert not is_valid_transition("enumerate", "recon")


def test_skip_transition_not_allowed():
    assert not is_valid_transition("recon", "probe")


def test_report_transition_from_any():
    for phase in ("recon", "enumerate", "probe", "verify"):
        assert is_valid_transition(phase, "report")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_phases.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/apps/agent/phases.py
from __future__ import annotations

PHASE_ORDER = ["recon", "enumerate", "probe", "verify", "report"]


def next_phase(current: str) -> str | None:
    try:
        idx = PHASE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 < len(PHASE_ORDER):
        return PHASE_ORDER[idx + 1]
    return None


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    if to_phase == "report":
        return from_phase in PHASE_ORDER and from_phase != "report"
    try:
        fi = PHASE_ORDER.index(from_phase)
        ti = PHASE_ORDER.index(to_phase)
    except ValueError:
        return False
    return ti == fi + 1
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_phases.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/phases.py backend/apps/agent/tests/test_phases.py
git commit -m "feat(agent): add phase transition validation"
```

### Task 18: Mission profiles

**Files:**
- Create: `backend/apps/agent/mission_profiles.py`
- Create: `backend/apps/agent/tests/test_mission_profiles.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_mission_profiles.py
import pytest
from apps.agent.mission_profiles import get_profile, MissionProfile


def test_juice_shop_scoreboard_profile():
    profile = get_profile("juice_shop_scoreboard")
    assert profile.objective == "Find the hidden admin scoreboard page"
    assert profile.phases == ["recon", "enumerate", "report"]
    assert profile.mission_budget["max_turns"] == 25
    assert "recon" in profile.phase_budgets


def test_unknown_profile_raises():
    with pytest.raises(KeyError):
        get_profile("nonexistent_profile")


def test_profile_has_all_budget_dimensions():
    profile = get_profile("juice_shop_scoreboard")
    for dim in ("max_turns", "max_http_requests", "max_asset_inspections"):
        assert dim in profile.mission_budget
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/apps/agent/mission_profiles.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissionProfile:
    name: str
    target: str
    objective: str
    success_category: str
    phases: list[str]
    mission_budget: dict[str, int]
    phase_budgets: dict[str, dict[str, int]]
    model_policy: dict[str, Any] = field(default_factory=dict)


_PROFILES: dict[str, MissionProfile] = {
    "juice_shop_scoreboard": MissionProfile(
        name="juice_shop_scoreboard",
        target="juiceshop.cocode.dk",
        objective="Find the hidden admin scoreboard page",
        success_category="hidden_route_discovered",
        phases=["recon", "enumerate", "report"],
        mission_budget={
            "max_turns": 25,
            "max_runtime_seconds": 300,
            "max_llm_calls": 30,
            "max_http_requests": 60,
            "max_browser_actions": 40,
            "max_asset_inspections": 10,
        },
        phase_budgets={
            "recon": {
                "max_turns": 6,
                "max_http_requests": 20,
                "max_asset_inspections": 5,
            },
            "enumerate": {
                "max_turns": 14,
                "max_http_requests": 35,
                "max_asset_inspections": 5,
            },
            "report": {
                "max_turns": 3,
                "max_http_requests": 0,
                "max_asset_inspections": 0,
            },
        },
    ),
}


def get_profile(name: str) -> MissionProfile:
    return _PROFILES[name]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/mission_profiles.py backend/apps/agent/tests/test_mission_profiles.py
git commit -m "feat(agent): add juice_shop_scoreboard mission profile"
```
