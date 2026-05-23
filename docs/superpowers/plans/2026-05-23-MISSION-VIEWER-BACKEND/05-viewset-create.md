# Task 5: Agent Viewset — Create (Start Mission)

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
        # Celery task enqueued on commit
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
Expected: FAIL — POST returns 400 because serializer doesn't accept `target`/`mission_profile` as write fields

- [ ] **Step 3: Add write fields to AgentSessionSerializer**

In `backend/apps/agent/serializers.py`, update `AgentSessionSerializer`:

```python
class AgentSessionSerializer(serializers.ModelSerializer):
    active_phases = serializers.SerializerMethodField()
    target_base_url = serializers.CharField(
        source="target.base_url", read_only=True,
    )
    target = serializers.PrimaryKeyRelatedField(
        queryset=ScanTarget.objects.all(),
    )
    mission_profile = serializers.CharField(
        default="juice_shop_scoreboard",
    )

    class Meta:
        model = AgentSession
        fields = (
            "id", "scan_run", "scan_target_run", "target",
            "status", "current_phase", "mission_profile",
            "autonomy_mode", "mission_budget", "consumed_budget",
            "progress_counters", "model_policy", "roe_snapshot",
            "started_at", "finished_at", "created_at", "updated_at",
            "active_phases", "target_base_url",
        )
        read_only_fields = (
            "id", "scan_run", "scan_target_run",
            "status", "current_phase",
            "autonomy_mode", "mission_budget", "consumed_budget",
            "progress_counters", "model_policy", "roe_snapshot",
            "started_at", "finished_at", "created_at", "updated_at",
            "active_phases", "target_base_url",
        )

    def get_active_phases(self, obj: AgentSession) -> list[str]:
        from .mission_profiles import get_profile
        try:
            profile = get_profile(obj.mission_profile)
            return profile.phases
        except KeyError:
            return [c.value for c in AgentPhase]

    def validate_mission_profile(self, value: str) -> str:
        from .mission_profiles import get_profile
        try:
            get_profile(value)
        except KeyError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, attrs: dict) -> dict:
        target = attrs["target"]
        active = AgentSession.objects.filter(
            target=target,
            status__in=["pending", "running", "paused"],
        ).exists()
        if active:
            raise serializers.ValidationError(
                {"target": "Target already has an active agent session."}
            )
        return attrs

    def create(self, validated_data: dict) -> AgentSession:
        from django.db import transaction

        from apps.events.types import EventType
        from apps.scans.models import ScanRun, ScanTargetRun

        from .event_log import emit_session_started
        from .mission_profiles import get_profile
        from .persistence import create_session

        target = validated_data["target"]
        profile_name = validated_data["mission_profile"]
        profile = get_profile(profile_name)

        with transaction.atomic():
            scan_run = ScanRun.objects.create(
                project=target.project,
                stub_slug="agent.v3",
            )
            scan_run.start()
            target_run = ScanTargetRun.objects.create(
                scan_run=scan_run, target=target,
            )
            session = create_session(
                scan_run=scan_run,
                target_run=target_run,
                target=target,
                mission_profile=profile_name,
                model_policy=profile.model_policy,
                mission_budget=profile.mission_budget,
            )
            emit_session_started(session)

        return session
```

Add the import at the top of `serializers.py`:

```python
from apps.targets.models import ScanTarget
```

- [ ] **Step 4: Add perform_create with on_commit enqueue to views.py**

In `backend/apps/agent/views.py`, update the viewset:

```python
from django.db import transaction


class AgentSessionViewSet(...):
    # ... existing methods ...

    def perform_create(self, serializer):
        session = serializer.save()
        transaction.on_commit(
            lambda: _enqueue_agent_session(str(session.id))
        )


def _enqueue_agent_session(session_id: str) -> None:
    from .tasks import run_agent_session
    run_agent_session.delay(session_id)
```

- [ ] **Step 5: Run create tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionCreateTests -v`
Expected: ALL PASS

- [ ] **Step 6: Write validation tests**

Add to `test_views.py`:

```python
class AgentSessionCreateValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="test.example.com", project=self.project,
        )

    def test_unknown_target_returns_400(self):
        import uuid
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(uuid.uuid4()),
        }, format="json")
        assert resp.status_code == 400

    def test_unknown_profile_returns_400(self):
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
            "mission_profile": "nonexistent",
        }, format="json")
        assert resp.status_code == 400

    def test_duplicate_active_session_returns_400(self):
        from apps.agent.models import (
            AgentSession, AutonomyMode, AgentPhase, SessionStatus,
        )
        run = ScanRun.objects.create(
            project=self.project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=self.target)
        AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=self.target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
        }, format="json")
        assert resp.status_code == 400
        assert "active" in str(resp.json()).lower()
```

- [ ] **Step 7: Run validation tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionCreateValidationTests -v`
Expected: ALL PASS

- [ ] **Step 8: Run full view test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add backend/apps/agent/serializers.py backend/apps/agent/views.py backend/apps/agent/tests/test_views.py
git commit -m "feat(agent): add start-mission POST with validation + Celery enqueue"
```
