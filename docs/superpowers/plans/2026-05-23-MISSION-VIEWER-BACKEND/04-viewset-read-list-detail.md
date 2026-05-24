---
tier: CAPABLE
depends_on:
  - 03-serializers-turn-session
files:
  creates:
    - backend/apps/agent/views.py
    - backend/apps/agent/tests/test_views.py
  modifies:
    - backend/config/urls.py
  deletes: []
  renames: []
  generated: []
exports:
  - name: AgentSessionViewSet
    file: backend/apps/agent/views.py
imports: []
allow_extra_files: false
---

# Task 4A: Viewset — List, Detail, Implementation

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

- [ ] **Step 4: Register viewset in urls.py (temporary — formalized in Task 9)**

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

Continues in [04-viewset-read-turns-notes.md](04-viewset-read-turns-notes.md).
