---
tier: CAPABLE
depends_on:
  - 04-viewset-read-turns-notes
  - 05-viewset-create-serializer
files:
  creates: []
  modifies:
    - backend/apps/agent/views.py
    - backend/apps/agent/tests/test_views.py
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 5A: Viewset Create — Success Path

**Files:**
- Modify: `backend/apps/agent/serializers.py`
- Modify: `backend/apps/agent/views.py`
- Modify: `backend/apps/agent/tests/test_views.py`

---

- [ ] **Step 1: Write test for successful mission creation**

Add to `backend/apps/agent/tests/test_views.py`:

```python
from unittest.mock import patch


class AgentSessionCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="juiceshop.cocode.dk", project=self.project,
            base_url="https://juiceshop.cocode.dk",
        )

    def test_create_returns_201_with_full_session(self):
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            resp = self.client.post(url, {
                "target": str(self.target.id),
                "mission_profile": "juice_shop_scoreboard",
            }, format="json")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "running"
        assert data["current_phase"] == "recon"
        assert data["mission_profile"] == "juice_shop_scoreboard"
        assert data["scan_run"] is not None
        assert data["scan_target_run"] is not None
        assert len(callbacks) == 1

    def test_create_creates_scan_run_and_target_run(self):
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(url, {
                "target": str(self.target.id),
            }, format="json")
        assert ScanRun.objects.filter(stub_slug="agent.v3").count() == 1
        assert ScanTargetRun.objects.count() == 1

    def test_create_emits_session_started_event(self):
        from apps.events.models import Event
        from apps.events.types import EventType
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(url, {
                "target": str(self.target.id),
            }, format="json")
        assert Event.objects.filter(
            type=EventType.AGENT_SESSION_STARTED
        ).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionCreateTests -v`
Expected: FAIL — POST returns 400

- [ ] **Step 3: Add write fields to AgentSessionSerializer**

In `backend/apps/agent/serializers.py`, update `AgentSessionSerializer` to
accept `target` and `mission_profile` as write fields. Add `validate_mission_profile`
and `validate` (duplicate active session check) and `create` (ScanRun + ScanTargetRun
+ AgentSession + emit). See [05-viewset-create-serializer.md](05-viewset-create-serializer.md)
for the full serializer code.

- [ ] **Step 4: Add perform_create with on_commit enqueue to views.py**

In `backend/apps/agent/views.py`, add:

```python
from django.db import transaction


class AgentSessionViewSet(...):
    def perform_create(self, serializer):
        session = serializer.save()
        transaction.on_commit(
            lambda: _enqueue_agent_session(str(session.id))
        )


def _enqueue_agent_session(session_id: str) -> None:
    from .tasks import run_agent_session
    run_agent_session.delay(session_id)
```

Task 8 creates `backend/apps/agent/tasks.py`. The tests in this task keep
`execute=False` so the callback is captured but not executed; do not run this
POST path with callbacks enabled until Task 8 is complete.

- [ ] **Step 5: Run create tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionCreateTests -v`
Expected: ALL PASS

Continues in [05-viewset-create-validation.md](05-viewset-create-validation.md).
