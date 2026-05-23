---
tier: CAPABLE
depends_on:
  - 03-serializers-observation-action-note
files:
  creates: []
  modifies:
    - backend/apps/agent/serializers.py
    - backend/apps/agent/tests/test_serializers.py
  deletes: []
  renames: []
  generated: []
exports:
  - name: AgentTurnSerializer
    file: backend/apps/agent/serializers.py
  - name: AgentSessionSerializer
    file: backend/apps/agent/serializers.py
imports: []
allow_extra_files: false
---

# Task 3B: Serializers — Turn + Session

Continues from [03-serializers-observation-action-note.md](03-serializers-observation-action-note.md).

**Files:**
- Modify: `backend/apps/agent/serializers.py`
- Modify: `backend/apps/agent/tests/test_serializers.py`

---

- [ ] **Step 11: Write tests for AgentTurnSerializer with nested actions and notes**

Add to `test_serializers.py`:

```python
from apps.agent.serializers import AgentTurnSerializer


@pytest.mark.django_db
class TestAgentTurnSerializer:
    def test_nests_actions_and_notes(self, create_session):
        from apps.agent.models import (
            AgentTurn, AgentAction, AgentNote, AgentObservation,
            TurnStatus, ValidationStatus, ExecutionStatus,
            ObservationType, NoteType,
        )
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=0, phase="recon", model="mock",
            input_tokens=100, output_tokens=50, status=TurnStatus.COMPLETED,
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
            session=session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/test"},
        )
        data = AgentTurnSerializer(turn).data
        assert data["index"] == 0
        assert data["input_tokens"] == 100
        assert len(data["actions"]) == 1
        assert len(data["actions"][0]["observations"]) == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["note_type"] == "route"
```

- [ ] **Step 12: Write AgentTurnSerializer**

Append to `backend/apps/agent/serializers.py`:

```python
from .models import AgentTurn


class AgentTurnSerializer(serializers.ModelSerializer):
    actions = AgentActionSerializer(many=True, read_only=True)
    notes = AgentTurnNoteSerializer(many=True, read_only=True)

    class Meta:
        model = AgentTurn
        fields = (
            "id", "index", "phase", "model", "input_tokens",
            "output_tokens", "cost_estimate", "status",
            "created_at", "finished_at", "actions", "notes",
        )
        read_only_fields = fields
```

- [ ] **Step 13: Run turn serializer test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentTurnSerializer -v`
Expected: PASS

- [ ] **Step 14: Write tests for AgentSessionSerializer**

Add to `test_serializers.py`:

```python
from apps.agent.serializers import AgentSessionSerializer


@pytest.mark.django_db
class TestAgentSessionSerializer:
    def test_read_fields_include_active_phases_and_target_url(self, create_session):
        session = create_session(mission_profile="juice_shop_scoreboard")
        data = AgentSessionSerializer(session).data
        assert data["active_phases"] == ["recon", "enumerate", "report"]
        assert data["target_base_url"] is not None
        assert "scan_run" in data
        assert "scan_target_run" in data

    def test_unknown_profile_returns_all_phases(self, create_session):
        session = create_session(mission_profile="unknown_profile")
        data = AgentSessionSerializer(session).data
        assert data["active_phases"] == [
            "recon", "enumerate", "probe", "verify", "report",
        ]
```

- [ ] **Step 15: Write AgentSessionSerializer**

Append to `backend/apps/agent/serializers.py`:

```python
from .models import AgentPhase, AgentSession


class AgentSessionSerializer(serializers.ModelSerializer):
    active_phases = serializers.SerializerMethodField()
    target_base_url = serializers.CharField(
        source="target.base_url", read_only=True,
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
        read_only_fields = fields

    def get_active_phases(self, obj: AgentSession) -> list[str]:
        from .mission_profiles import get_profile
        try:
            profile = get_profile(obj.mission_profile)
            return profile.phases
        except KeyError:
            return [c.value for c in AgentPhase]
```

- [ ] **Step 16: Run session serializer test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentSessionSerializer -v`
Expected: PASS

- [ ] **Step 17: Run full serializer test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py -v`
Expected: ALL PASS

- [ ] **Step 18: Commit**

```bash
git add backend/apps/agent/serializers.py backend/apps/agent/tests/test_serializers.py
git commit -m "feat(agent): add DRF serializers for session/turn/action/observation/note"
```
