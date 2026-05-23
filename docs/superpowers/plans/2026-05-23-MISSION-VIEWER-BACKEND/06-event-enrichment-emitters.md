---
tier: CAPABLE
depends_on:
  - 06-event-enrichment-helpers
files:
  creates: []
  modifies:
    - backend/apps/agent/event_log.py
    - backend/apps/agent/tests/test_event_log.py
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 6B: Event Enrichment — Emitter Signatures

Continues from [06-event-enrichment-helpers.md](06-event-enrichment-helpers.md).

**Files:**
- Modify: `backend/apps/agent/event_log.py`
- Modify: `backend/apps/agent/tests/test_event_log.py`

---

- [ ] **Step 8: Write test for enriched emit_action_executed**

Add to `test_event_log.py`:

```python
from apps.agent.event_log import emit_action_executed


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

```python
from apps.agent.event_log import emit_action_denied


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

- [ ] **Step 14: Write tests + update emit_phase_changed and emit_mission_finished**

```python
from apps.agent.event_log import emit_phase_changed, emit_mission_finished


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

Update `emit_phase_changed` to accept `budget_snapshot: dict | None = None`
and include it in `data`. Same for `emit_mission_finished`.

- [ ] **Step 15: Run all enrichment tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py -v`
Expected: ALL PASS

- [ ] **Step 16: Commit**

```bash
git add backend/apps/agent/event_log.py backend/apps/agent/tests/test_event_log.py
git commit -m "feat(agent): enrich event payloads with budget snapshot + observation summary"
```
