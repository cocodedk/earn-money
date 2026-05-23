---
tier: CAPABLE
depends_on:
  - 04-viewset-read-list-detail
files:
  creates: []
  modifies:
    - backend/apps/agent/tests/test_views.py
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 4B: Viewset — Turns, Notes, Read-Only Guards

Continues from [04-viewset-read-list-detail.md](04-viewset-read-list-detail.md).

**Files:**
- Modify: `backend/apps/agent/tests/test_views.py`

---

- [ ] **Step 8: Write test for turns endpoint with nested data**

Add to `test_views.py`:

```python
class AgentSessionTurnsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import (
            AgentSession, AgentTurn, AgentAction, AgentObservation,
            AgentNote, AutonomyMode, AgentPhase, TurnStatus,
            ValidationStatus, ExecutionStatus, ObservationType, NoteType,
        )
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        turn = AgentTurn.objects.create(
            session=self.session, index=0, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
        )
        action = AgentAction.objects.create(
            turn=turn, action_type="observe_page", args_redacted={},
            validation_status=ValidationStatus.VALID,
            execution_status=ExecutionStatus.EXECUTED,
        )
        AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"},
        )
        AgentNote.objects.create(
            session=self.session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/test"},
        )

    def test_turns_endpoint_nests_actions_observations_notes(self):
        url = reverse("agent-session-turns", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        turn = results[0]
        assert turn["index"] == 0
        assert len(turn["actions"]) == 1
        assert len(turn["actions"][0]["observations"]) == 1
        assert len(turn["notes"]) == 1

    def test_turns_ordered_by_index(self):
        from apps.agent.models import AgentTurn, TurnStatus
        AgentTurn.objects.create(
            session=self.session, index=1, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
        )
        url = reverse("agent-session-turns", args=[self.session.id])
        results = self.client.get(url).json()["results"]
        assert results[0]["index"] == 0
        assert results[1]["index"] == 1
```

- [ ] **Step 9: Run turns tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionTurnsTests -v`
Expected: PASS

- [ ] **Step 10: Write test for notes endpoint**

Add to `test_views.py`:

```python
class AgentSessionNotesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import (
            AgentSession, AgentTurn, AgentNote, AutonomyMode,
            AgentPhase, TurnStatus, NoteType,
        )
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        turn = AgentTurn.objects.create(
            session=self.session, index=5, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
        )
        AgentNote.objects.create(
            session=self.session, turn=turn,
            note_type=NoteType.HYPOTHESIS,
            content={"text": "test"},
        )

    def test_notes_includes_turn_index(self):
        url = reverse("agent-session-notes", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        note = resp.json()["results"][0]
        assert note["turn_index"] == 5
        assert note["note_type"] == "hypothesis"
```

- [ ] **Step 11: Run notes test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionNotesTests -v`
Expected: PASS

- [ ] **Step 12: Write test that update/destroy return 405**

Add to `test_views.py`:

```python
class AgentSessionReadOnlyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )

    def test_put_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.put(url, {}).status_code == 405

    def test_patch_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.patch(url, {}).status_code == 405

    def test_delete_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.delete(url).status_code == 405
```

- [ ] **Step 13: Run read-only tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionReadOnlyTests -v`
Expected: PASS

- [ ] **Step 14: Run full view test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py -v`
Expected: ALL PASS

- [ ] **Step 15: Commit**

```bash
git add backend/apps/agent/views.py backend/apps/agent/tests/test_views.py backend/config/urls.py
git commit -m "feat(agent): add AgentSessionViewSet with list/retrieve/turns/notes"
```
