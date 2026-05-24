# V3 Slice 3 — Warm-Start Target Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a mission runs against a previously-probed target, seed the LLM with compact prior intel and the plateau detector with known routes — accelerating exploration without fabricating evidence.

**Architecture:** New `target_intel.py` module builds a `TargetIntel` dataclass from the most recent completed session. The system prompt gets an optional `## Prior Target Intel` section. PlateauDetector accepts an optional `known_routes` baseline. The Celery task queries prior sessions and wires intel through to the controller.

**Tech Stack:** Django ORM, Python dataclasses, pytest

---

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/apps/agent/target_intel.py` | Create | `TargetIntel`, `FormSignature`, `PriorCandidate` dataclasses + `build_target_intel()` + `format_intel_prompt()` |
| `backend/apps/agent/plateau.py` | Modify | Accept optional `known_routes` baseline in constructor |
| `backend/apps/agent/llm/prompts.py` | Modify | Accept optional `prior_intel_section` param in `build_system_prompt()` |
| `backend/apps/agent/controller.py` | Modify | Accept optional `target_intel` param, pass to prompt and plateau |
| `backend/apps/agent/tasks.py` | Modify | Query prior session, build intel, pass to controller |
| `backend/apps/agent/tests/test_target_intel.py` | Create | Tests for `build_target_intel()` and `format_intel_prompt()` |
| `backend/apps/agent/tests/test_plateau.py` | Modify | Tests for baseline route filtering |
| `backend/apps/agent/tests/test_prompts.py` | Modify | Tests for prior intel section in prompt |
| `backend/apps/agent/tests/test_controller.py` | Modify | Tests for warm-start wiring through controller |

---

### Task 1: TargetIntel dataclasses and build_target_intel()

**Files:**
- Create: `backend/apps/agent/target_intel.py`
- Create: `backend/apps/agent/tests/test_target_intel.py`

- [ ] **Step 1: Write failing tests for TargetIntel construction**

Create `backend/apps/agent/tests/test_target_intel.py`:

```python
from __future__ import annotations

import pytest
from datetime import timedelta
from django.utils import timezone

from apps.agent.target_intel import (
    FormSignature, PriorCandidate, TargetIntel,
    build_target_intel, format_intel_prompt,
)


@pytest.fixture
def target_with_session(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget
    from apps.agent.persistence import create_session
    from apps.agent.models import SessionStatus

    project = Project.objects.create(name="intel-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    session.status = SessionStatus.COMPLETED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at"])
    return {"target": target, "session": session, "scan_run": scan_run}


class TestBuildTargetIntelNoSession:
    @pytest.mark.django_db
    def test_returns_none_without_prior_session(self, db):
        from apps.projects.models import Project
        from apps.targets.models import ScanTarget

        project = Project.objects.create(name="no-session")
        target = ScanTarget.objects.create(host="fresh.example.com", project=project)
        result = build_target_intel(target, stale_after_days=7)
        assert result is None


@pytest.mark.django_db
class TestBuildTargetIntelWithSession:
    def test_returns_target_intel(self, target_with_session):
        target = target_with_session["target"]
        intel = build_target_intel(target, stale_after_days=7)
        assert isinstance(intel, TargetIntel)
        assert intel.source_session_id == str(target_with_session["session"].pk)

    def test_fresh_session_not_stale(self, target_with_session):
        target = target_with_session["target"]
        intel = build_target_intel(target, stale_after_days=7)
        assert intel.is_stale is False

    def test_old_session_is_stale(self, target_with_session):
        session = target_with_session["session"]
        session.finished_at = timezone.now() - timedelta(days=10)
        session.save(update_fields=["finished_at"])
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert intel.is_stale is True


@pytest.mark.django_db
class TestBuildTargetIntelRoutes:
    def test_extracts_routes_from_notes(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "route", {"path": "/#!/score-board"})
        record_note(session, turn, "route", {"path": "/api/Challenges"})

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert "/#!/score-board" in intel.known_routes
        assert "/api/Challenges" in intel.known_routes

    def test_hash_routes_preserved(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "route", {"path": "/#!/login"})

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert "/#!/login" in intel.known_routes

    def test_max_routes_cap(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        for i in range(25):
            record_note(session, turn, "route", {"path": f"/route/{i}"})

        intel = build_target_intel(
            target_with_session["target"], stale_after_days=7, max_routes=10,
        )
        assert len(intel.known_routes) == 10


@pytest.mark.django_db
class TestBuildTargetIntelCandidates:
    def test_extracts_candidates(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn
        from apps.agent.models import AgentAction, ValidationStatus, ExecutionStatus
        turn = create_turn(session, model="mock")
        AgentAction.objects.create(
            turn=turn, action_type="submit_candidate",
            args_redacted={}, goal="found scoreboard",
            reason="r", hypothesis="h",
            validation_status=ValidationStatus.VALID,
            execution_status=ExecutionStatus.EXECUTED,
        )

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert len(intel.prior_candidates) == 1
        assert intel.prior_candidates[0].description == "found scoreboard"


@pytest.mark.django_db
class TestFormatIntelPrompt:
    def test_returns_empty_for_none(self):
        assert format_intel_prompt(None) == ""

    def test_includes_source_session(self, target_with_session):
        target = target_with_session["target"]
        intel = build_target_intel(target, stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "Prior Target Intel" in prompt
        assert str(intel.source_session_id) in prompt

    def test_stale_label_present(self, target_with_session):
        session = target_with_session["session"]
        session.finished_at = timezone.now() - timedelta(days=10)
        session.save(update_fields=["finished_at"])
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "stale" in prompt

    def test_fresh_label_present(self, target_with_session):
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "fresh" in prompt

    def test_deterministic_output(self, target_with_session):
        target = target_with_session["target"]
        a = format_intel_prompt(build_target_intel(target, stale_after_days=7))
        b = format_intel_prompt(build_target_intel(target, stale_after_days=7))
        assert a == b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_target_intel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.agent.target_intel'`

- [ ] **Step 3: Implement target_intel.py**

Create `backend/apps/agent/target_intel.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.utils import timezone


@dataclass
class FormSignature:
    action: str
    method: str
    input_names: list[str]


@dataclass
class PriorCandidate:
    category: str
    description: str


@dataclass
class TargetIntel:
    source_session_id: str
    source_completed_at: datetime
    is_stale: bool
    known_routes: set[str] = field(default_factory=set)
    form_signatures: list[FormSignature] = field(default_factory=list)
    prior_candidates: list[PriorCandidate] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)


def build_target_intel(
    target,
    *,
    stale_after_days: int = 7,
    max_routes: int = 20,
    max_forms: int = 10,
    max_candidates: int = 10,
    max_notes: int = 5,
) -> TargetIntel | None:
    from .models import AgentSession, SessionStatus

    prior = (
        AgentSession.objects.filter(
            target=target,
            status=SessionStatus.COMPLETED,
        )
        .order_by("-finished_at")
        .first()
    )
    if prior is None or prior.finished_at is None:
        return None

    is_stale = (timezone.now() - prior.finished_at) > timedelta(days=stale_after_days)

    routes = _extract_routes(prior, max_routes)
    candidates = _extract_candidates(prior, max_candidates)
    hypotheses = _extract_hypotheses(prior, max_notes)

    return TargetIntel(
        source_session_id=str(prior.pk),
        source_completed_at=prior.finished_at,
        is_stale=is_stale,
        known_routes=routes,
        prior_candidates=candidates,
        hypotheses=hypotheses,
    )


def _extract_routes(session, max_routes: int) -> set[str]:
    notes = session.notes.filter(note_type="route").values_list("content", flat=True)
    routes: set[str] = set()
    for content in notes:
        path = content.get("path", "") if isinstance(content, dict) else ""
        if path:
            routes.add(path)
        if len(routes) >= max_routes:
            break
    return routes


def _extract_candidates(session, max_candidates: int) -> list[PriorCandidate]:
    from .models import AgentAction, ValidationStatus

    actions = AgentAction.objects.filter(
        turn__session=session,
        action_type="submit_candidate",
        validation_status=ValidationStatus.VALID,
    ).values("goal", "args_redacted")[:max_candidates]

    return [
        PriorCandidate(
            category=a["args_redacted"].get("category", "unknown"),
            description=a["goal"][:200],
        )
        for a in actions
    ]


def _extract_hypotheses(session, max_notes: int) -> list[str]:
    notes = (
        session.notes.filter(note_type__in=["hypothesis", "gap"])
        .values_list("content", flat=True)[:max_notes]
    )
    results = []
    for content in notes:
        if isinstance(content, dict):
            text = content.get("text", "") or content.get("description", "")
            if text:
                results.append(text[:200])
    return results


def format_intel_prompt(intel: TargetIntel | None) -> str:
    if intel is None:
        return ""
    freshness = "stale — treat with lower confidence" if intel.is_stale else "fresh"
    date_str = intel.source_completed_at.strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "## Prior Target Intel",
        "",
        f"Source session: {intel.source_session_id}, completed at {date_str}",
        f"Freshness: {freshness}",
        "",
        "These are unverified hints from a previous session. You must re-observe",
        "to get current element IDs. Prior candidates are re-check targets,",
        "not current evidence.",
    ]

    if intel.known_routes:
        lines.append("")
        lines.append("Known routes:")
        for route in sorted(intel.known_routes):
            lines.append(f"  {route}")

    if intel.prior_candidates:
        lines.append("")
        lines.append("Prior candidates to re-check:")
        for c in intel.prior_candidates:
            lines.append(f"  - category: {c.category}")
            lines.append(f"    description: {c.description}")
            lines.append("    instruction: re-verify in current session")

    if intel.hypotheses:
        lines.append("")
        lines.append("Gaps / hypotheses:")
        for h in intel.hypotheses:
            lines.append(f"  - {h}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_target_intel.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/target_intel.py backend/apps/agent/tests/test_target_intel.py
git commit -m "feat(agent): add TargetIntel dataclass and build_target_intel()"
```

---

### Task 2: PlateauDetector baseline routes

**Files:**
- Modify: `backend/apps/agent/plateau.py`
- Modify: `backend/apps/agent/tests/test_plateau.py`

- [ ] **Step 1: Write failing tests for baseline filtering**

Add to `test_plateau.py`:

```python
class TestBaselineRoutes:
    def test_known_route_does_not_reset_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login", "/admin"},
        )
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/login"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is True

    def test_novel_route_resets_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login"},
        )
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/new-page"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False

    def test_no_baseline_means_all_routes_novel(self):
        pd = PlateauDetector(max_turns_without_new_route=2)
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/login"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False

    def test_mixed_known_and_novel(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login"},
        )
        pd.record_turn(
            new_routes=2, new_elements=0,
            route_paths=["/login", "/new-page"],
        )
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_plateau.py::TestBaselineRoutes -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'known_routes'`

- [ ] **Step 3: Implement baseline in PlateauDetector**

Modify `plateau.py` `__init__` to accept `known_routes` and `record_turn` to accept `route_paths`:

```python
def __init__(
    self,
    max_turns_without_new_route: int = 3,
    max_turns_without_new_interactive_element: int = 3,
    max_repeated_denials: int = 3,
    max_invalid_actions: int = 2,
    known_routes: set[str] | None = None,
) -> None:
    self._max_no_route = max_turns_without_new_route
    self._max_no_element = max_turns_without_new_interactive_element
    self._max_denials = max_repeated_denials
    self._max_invalid = max_invalid_actions
    self._known_routes: set[str] = set(known_routes) if known_routes else set()

    self._turns_no_route: int = 0
    self._turns_no_element: int = 0
    self._denial_streak: int = 0
    self._invalid_streak: int = 0

def record_turn(
    self,
    new_routes: int,
    new_elements: int,
    route_paths: list[str] | None = None,
) -> None:
    novel_routes = new_routes
    if route_paths is not None and self._known_routes:
        novel_routes = sum(
            1 for p in route_paths if p not in self._known_routes
        )

    if novel_routes > 0:
        self._turns_no_route = 0
    else:
        self._turns_no_route += 1

    if new_elements > 0:
        self._turns_no_element = 0
    else:
        self._turns_no_element += 1

    if novel_routes > 0 or new_elements > 0:
        self._denial_streak = 0
        self._invalid_streak = 0
```

- [ ] **Step 4: Run ALL plateau tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_plateau.py -v`
Expected: ALL PASS (existing tests don't pass route_paths, so novel_routes == new_routes — backward compatible)

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/plateau.py backend/apps/agent/tests/test_plateau.py
git commit -m "feat(agent): add known_routes baseline to PlateauDetector"
```

---

### Task 3: Extend build_system_prompt with prior intel section

**Files:**
- Modify: `backend/apps/agent/llm/prompts.py`
- Modify: `backend/apps/agent/tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Add to `test_prompts.py`:

```python
class TestPriorIntelSection:
    def test_no_intel_means_no_section(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
        )
        assert "Prior Target Intel" not in prompt

    def test_intel_section_injected(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
            prior_intel_section="## Prior Target Intel\nKnown routes:\n  /login",
        )
        assert "Prior Target Intel" in prompt
        assert "/login" in prompt

    def test_intel_section_appears_after_budget(self):
        prompt = build_system_prompt(
            objective="test", phase="recon",
            allowed_actions=["observe_page", "stop"],
            budget_remaining=10,
            prior_intel_section="## Prior Target Intel\ntest",
        )
        budget_pos = prompt.index("Remaining turns")
        intel_pos = prompt.index("Prior Target Intel")
        safety_pos = prompt.index("Safety Rules")
        assert budget_pos < intel_pos < safety_pos
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py::TestPriorIntelSection -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'prior_intel_section'`

- [ ] **Step 3: Implement prior_intel_section in build_system_prompt**

Modify `build_system_prompt` signature and `_SYSTEM_HEADER`:

Add `{prior_intel}` placeholder in `_SYSTEM_HEADER` between Budget and Safety Rules:

```python
## Budget
Remaining turns: {budget_remaining}

{prior_intel}
## Safety Rules
```

Update `build_system_prompt`:

```python
def build_system_prompt(
    objective: str,
    phase: str,
    allowed_actions: list[str],
    budget_remaining: int,
    prior_intel_section: str = "",
) -> str:
    actions_str = "\n".join(f"  - {a}" for a in sorted(allowed_actions))
    action_schemas = _build_action_schemas(allowed_actions)
    return _SYSTEM_HEADER.format(
        objective=objective,
        phase=phase,
        allowed_actions=actions_str,
        budget_remaining=budget_remaining,
        prior_intel=prior_intel_section,
        action_schemas=action_schemas,
    )
```

- [ ] **Step 4: Run ALL prompt tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_prompts.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/llm/prompts.py backend/apps/agent/tests/test_prompts.py
git commit -m "feat(agent): add optional prior_intel_section to system prompt"
```

---

### Task 4: Wire target intel through MissionController

**Files:**
- Modify: `backend/apps/agent/controller.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestWarmStart:
    @pytest.mark.asyncio
    async def test_prior_intel_in_system_prompt(self, db_objects):
        from apps.agent.target_intel import TargetIntel
        from django.utils import timezone

        intel = TargetIntel(
            source_session_id="prev-123",
            source_completed_at=timezone.now(),
            is_stale=False,
            known_routes={"/login", "/admin"},
        )
        c = _ctrl(db_objects, [_action_json("stop")], budget={"max_turns": 5})
        c.target_intel = intel
        prompt = c.system_prompt
        assert "Prior Target Intel" in prompt
        assert "/login" in prompt

    @pytest.mark.asyncio
    async def test_no_intel_means_no_section(self, db_objects):
        c = _ctrl(db_objects, [_action_json("stop")], budget={"max_turns": 5})
        prompt = c.system_prompt
        assert "Prior Target Intel" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestWarmStart -v`
Expected: FAIL — controller doesn't accept or use target_intel

- [ ] **Step 3: Implement target_intel in controller**

Modify `MissionController.__init__` to accept `target_intel`:

```python
def __init__(
    self,
    session,
    provider,
    driver,
    objective: str,
    mission_budget: dict,
    phase_budgets: dict | None = None,
    model_name: str = "mock",
    mission_phases: list[str] | None = None,
    target_intel=None,
) -> None:
    ...
    self.target_intel = target_intel
    known_routes = target_intel.known_routes if target_intel else None
    self.plateau = PlateauDetector(known_routes=known_routes)
    ...
```

Modify `system_prompt` property:

```python
@property
def system_prompt(self) -> str:
    from .target_intel import format_intel_prompt
    phase = self.session.current_phase
    intel_section = format_intel_prompt(self.target_intel)
    return build_system_prompt(
        objective=self.objective,
        phase=phase,
        allowed_actions=allowed_actions_for_phase(phase),
        budget_remaining=self.budget.remaining("turns"),
        prior_intel_section=intel_section,
    )
```

- [ ] **Step 4: Run ALL controller tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): wire target_intel through MissionController"
```

---

### Task 5: Wire target intel in Celery task

**Files:**
- Modify: `backend/apps/agent/tasks.py`

- [ ] **Step 1: Implement prior session query in _execute_agent_session**

In `tasks.py`, after `profile = get_profile(...)` (line 72), add:

```python
from .target_intel import build_target_intel
target_intel = build_target_intel(
    session.target,
    stale_after_days=7,
)
```

Pass to MissionController:

```python
ctrl = MissionController(
    session=session,
    provider=provider,
    driver=driver,
    objective=profile.objective,
    mission_budget=profile.mission_budget,
    phase_budgets=profile.phase_budgets,
    model_name=session.model_policy.get("model", "mock"),
    mission_phases=profile.phases,
    target_intel=target_intel,
)
```

- [ ] **Step 2: Run full test suite**

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS (existing tests use mock sessions that have no prior completed sessions, so target_intel is None)

- [ ] **Step 3: Commit**

```bash
git add backend/apps/agent/tasks.py
git commit -m "feat(agent): query prior session and pass target_intel to controller"
```

---

### Task 6: Pass route_paths through dispatch to plateau

**Files:**
- Modify: `backend/apps/agent/controller_dispatch.py`

- [ ] **Step 1: Update _execute_browser_action to pass route_paths**

In `controller_dispatch.py`, modify `_execute_browser_action` to pass discovered route paths to `record_turn`:

```python
new_routes = len(obs.discovered.routes)
route_paths = [r.path for r in obs.discovered.routes]
new_elements = (
    len(obs.elements.links) + len(obs.elements.buttons)
    + len(obs.elements.inputs) + len(obs.elements.forms)
)
ctrl.plateau.record_turn(
    new_routes=new_routes,
    new_elements=new_elements,
    route_paths=route_paths,
)
```

- [ ] **Step 2: Run full test suite**

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py
git commit -m "feat(agent): pass route_paths to plateau detector for baseline filtering"
```
