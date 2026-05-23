# Task 4: Agent Viewset — List, Retrieve, Turns, Notes

**Files:**
- Create: `backend/apps/agent/views.py`
- Create: `backend/apps/agent/tests/test_views.py`

---

- [ ] **Step 1: Write test for session list endpoint**

Create `backend/apps/agent/tests/test_views.py`:

```python
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.agent.models import SessionStatus
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


class AgentSessionListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="test.example.com", project=self.project,
        )
        run = ScanRun.objects.create(
            project=self.project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=self.target)
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=self.target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="juice_shop_scoreboard",
        )

    def test_list_returns_200_with_paginated_shape(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert "results" in resp.json()
        assert len(resp.json()["results"]) == 1

    def test_filter_by_status(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url, {"status": "running"})
        assert len(resp.json()["results"]) == 1
        resp = self.client.get(url, {"status": "completed"})
        assert len(resp.json()["results"]) == 0

    def test_filter_by_target(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url, {"target": str(self.target.id)})
        assert len(resp.json()["results"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionListTests -v`
Expected: FAIL — `NoReverseMatch: 'agent-session-list'`

- [ ] **Step 3: Write AgentSessionViewSet (list + retrieve)**

Create `backend/apps/agent/views.py`:

```python
from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import AgentSession
from .serializers import (
    AgentNoteSerializer,
    AgentSessionSerializer,
    AgentTurnSerializer,
)


class AgentSessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AgentSessionSerializer

    def get_queryset(self):
        qs = AgentSession.objects.select_related(
            "target", "scan_run",
        ).order_by("-created_at")
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("target"):
            qs = qs.filter(target_id=params["target"])
        return qs

    @action(detail=True, methods=["get"])
    def turns(self, _request: Request, pk=None) -> Response:
        session = self.get_object()
        qs = session.turns.prefetch_related(
            "actions__observations", "notes",
        ).order_by("index")
        page = self.paginate_queryset(qs)
        serializer = AgentTurnSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def notes(self, _request: Request, pk=None) -> Response:
        session = self.get_object()
        qs = session.notes.select_related("turn").order_by("created_at")
        page = self.paginate_queryset(qs)
        serializer = AgentNoteSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
```

- [ ] **Step 4: Register viewset in urls.py (temporary — will be formalized in Task 9)**

In `backend/config/urls.py`, add import and registration:

```python
from apps.agent.views import AgentSessionViewSet

router.register(r"agent/sessions", AgentSessionViewSet, basename="agent-session")
```

- [ ] **Step 5: Run list tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionListTests -v`
Expected: ALL PASS

- [ ] **Step 6: Write test for session detail**

Add to `test_views.py`:

```python
class AgentSessionDetailTests(TestCase):
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
            mission_profile="juice_shop_scoreboard",
        )

    def test_detail_includes_active_phases_and_target_url(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_phases"] == ["recon", "enumerate", "report"]
        assert data["target_base_url"] is not None
        assert data["scan_run"] is not None
```

- [ ] **Step 7: Run detail test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionDetailTests -v`
Expected: PASS

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
