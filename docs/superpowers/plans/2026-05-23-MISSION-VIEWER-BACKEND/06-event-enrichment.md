# Task 6: Event Enrichment — Budget Snapshot + Observation Summary

**Files:**
- Modify: `backend/apps/agent/event_log.py`
- Modify: `backend/apps/agent/tests/test_event_log.py`

---

- [ ] **Step 1: Write test for build_budget_snapshot helper**

Add to `backend/apps/agent/tests/test_event_log.py`:

```python
import pytest
from apps.agent.event_log import build_budget_snapshot


@pytest.mark.django_db
class TestBuildBudgetSnapshot:
    def test_returns_phase_consumed_and_mission_budget(self, create_session):
        session = create_session(
            mission_budget={"max_turns": 25, "max_http_requests": 60},
        )
        session.current_phase = "enumerate"
        consumed = {"mission": {"turns": 4}, "phase": {"turns": 2}}
        result = build_budget_snapshot(session, consumed)
        assert result == {
            "phase": "enumerate",
            "consumed": consumed,
            "mission_budget": {"max_turns": 25, "max_http_requests": 60},
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestBuildBudgetSnapshot -v`
Expected: FAIL — `ImportError: cannot import name 'build_budget_snapshot'`

- [ ] **Step 3: Write build_budget_snapshot**

Add to `backend/apps/agent/event_log.py`:

```python
def build_budget_snapshot(session: AgentSession, consumed: dict) -> dict:
    return {
        "phase": session.current_phase,
        "consumed": consumed,
        "mission_budget": session.mission_budget,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestBuildBudgetSnapshot -v`
Expected: PASS

- [ ] **Step 5: Write test for summarize_observation**

Add to `test_event_log.py`:

```python
from apps.agent.event_log import summarize_observation


class TestSummarizeObservation:
    def test_extracts_compact_summary(self):
        obs = {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "discovered": {
                "routes": ["/", "/rest/products"],
                "assets": ["/main.js"],
            },
            "elements": {
                "links": [{"href": "/"}],
                "buttons": [{"text": "Login"}, {"text": "Search"}],
                "forms": [{"action": "/rest/user/login"}],
            },
            "network": [{"url": "/rest/products"}, {"url": "/api/Challenges"}],
        }
        result = summarize_observation(obs)
        assert result == {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "route_count": 2,
            "asset_count": 1,
            "element_count": 4,
            "network_count": 2,
        }

    def test_handles_empty_observation(self):
        result = summarize_observation({})
        assert result == {
            "url": "",
            "title": "",
            "route_count": 0,
            "asset_count": 0,
            "element_count": 0,
            "network_count": 0,
        }
```

- [ ] **Step 6: Write summarize_observation**

Add to `backend/apps/agent/event_log.py`:

```python
def summarize_observation(obs_dict: dict) -> dict:
    return {
        "url": obs_dict.get("url", ""),
        "title": obs_dict.get("title", ""),
        "route_count": len(obs_dict.get("discovered", {}).get("routes", [])),
        "asset_count": len(obs_dict.get("discovered", {}).get("assets", [])),
        "element_count": (
            len(obs_dict.get("elements", {}).get("links", []))
            + len(obs_dict.get("elements", {}).get("buttons", []))
            + len(obs_dict.get("elements", {}).get("forms", []))
        ),
        "network_count": len(obs_dict.get("network", [])),
    }
```

- [ ] **Step 7: Run summarize test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestSummarizeObservation -v`
Expected: PASS

- [ ] **Step 8: Write test for enriched emit_action_executed**

Add to `test_event_log.py`:

```python
@pytest.mark.django_db
class TestEnrichedActionExecuted:
    def test_includes_goal_reason_hypothesis_budget_obs(self, create_session):
        session = create_session()
        event = emit_action_executed(
            session, turn_index=3, action_type="observe_page",
            goal="Inspect page", reason="Find nav links",
            hypothesis="Score-board in JS",
            budget_snapshot={"phase": "recon", "consumed": {}, "mission_budget": {}},
            observation_summary={"url": "https://example.com", "title": "Test",
                                 "route_count": 2, "asset_count": 1,
                                 "element_count": 5, "network_count": 3},
        )
        assert event.data["goal"] == "Inspect page"
        assert event.data["reason"] == "Find nav links"
        assert event.data["hypothesis"] == "Score-board in JS"
        assert event.data["budget_snapshot"]["phase"] == "recon"
        assert event.data["observation_summary"]["route_count"] == 2
```

- [ ] **Step 9: Update emit_action_executed signature**

In `backend/apps/agent/event_log.py`, replace `emit_action_executed`:

```python
def emit_action_executed(
    session: AgentSession,
    turn_index: int,
    action_type: str,
    goal: str = "",
    reason: str = "",
    hypothesis: str = "",
    budget_snapshot: dict | None = None,
    observation_summary: dict | None = None,
) -> Event:
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
            "goal": goal,
            "reason": reason,
            "hypothesis": hypothesis,
            "budget_snapshot": budget_snapshot or {},
            "observation_summary": observation_summary or {},
        },
    )
```

- [ ] **Step 10: Run enriched action test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestEnrichedActionExecuted -v`
Expected: PASS

- [ ] **Step 11: Write test for enriched emit_action_denied**

Add to `test_event_log.py`:

```python
@pytest.mark.django_db
class TestEnrichedActionDenied:
    def test_includes_goal_hypothesis_budget(self, create_session):
        session = create_session()
        event = emit_action_denied(
            session, turn_index=2, action_type="http_request",
            reason="Denied by phase",
            goal="Send request", hypothesis="Endpoint exposes users",
            budget_snapshot={"phase": "recon", "consumed": {}, "mission_budget": {}},
        )
        assert event.data["goal"] == "Send request"
        assert event.data["hypothesis"] == "Endpoint exposes users"
        assert event.data["budget_snapshot"]["phase"] == "recon"
```

- [ ] **Step 12: Update emit_action_denied signature**

Replace `emit_action_denied`:

```python
def emit_action_denied(
    session: AgentSession,
    turn_index: int,
    action_type: str,
    reason: str,
    goal: str = "",
    hypothesis: str = "",
    budget_snapshot: dict | None = None,
) -> Event:
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
            "goal": goal,
            "hypothesis": hypothesis,
            "budget_snapshot": budget_snapshot or {},
        },
    )
```

- [ ] **Step 13: Run denied test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestEnrichedActionDenied -v`
Expected: PASS

- [ ] **Step 14: Write tests for enriched phase_changed and mission_finished**

Add to `test_event_log.py`:

```python
@pytest.mark.django_db
class TestEnrichedPhaseChanged:
    def test_includes_budget_snapshot(self, create_session):
        session = create_session()
        event = emit_phase_changed(
            session, from_phase="recon", to_phase="enumerate",
            reason="plateau",
            budget_snapshot={"phase": "recon", "consumed": {}, "mission_budget": {}},
        )
        assert event.data["budget_snapshot"]["phase"] == "recon"


@pytest.mark.django_db
class TestEnrichedMissionFinished:
    def test_includes_budget_snapshot(self, create_session):
        session = create_session()
        event = emit_mission_finished(
            session, status="completed", reason="stop_action",
            budget_snapshot={"phase": "report", "consumed": {}, "mission_budget": {}},
        )
        assert event.data["budget_snapshot"]["phase"] == "report"
```

- [ ] **Step 15: Update emit_phase_changed and emit_mission_finished**

Replace `emit_phase_changed`:

```python
def emit_phase_changed(
    session: AgentSession,
    from_phase: str,
    to_phase: str,
    reason: str,
    budget_snapshot: dict | None = None,
) -> Event:
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
            "budget_snapshot": budget_snapshot or {},
        },
    )
```

Replace `emit_mission_finished`:

```python
def emit_mission_finished(
    session: AgentSession,
    status: str,
    reason: str,
    budget_snapshot: dict | None = None,
) -> Event:
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
            "budget_snapshot": budget_snapshot or {},
        },
    )
```

- [ ] **Step 16: Run all enrichment tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py -v`
Expected: ALL PASS

- [ ] **Step 17: Commit**

```bash
git add backend/apps/agent/event_log.py backend/apps/agent/tests/test_event_log.py
git commit -m "feat(agent): enrich event payloads with budget snapshot + observation summary"
```
