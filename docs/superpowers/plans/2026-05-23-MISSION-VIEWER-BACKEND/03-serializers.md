# Task 3: Agent Serializers

**Files:**
- Create: `backend/apps/agent/serializers.py`
- Create: `backend/apps/agent/tests/test_serializers.py`

---

- [ ] **Step 1: Write tests for AgentObservationSerializer**

Create `backend/apps/agent/tests/test_serializers.py`:

```python
import pytest
from apps.agent.models import ObservationType, ValidationStatus, ExecutionStatus
from apps.agent.serializers import AgentObservationSerializer


@pytest.mark.django_db
class TestAgentObservationSerializer:
    def test_fields(self, create_action):
        from apps.agent.models import AgentObservation
        action = create_action()
        obs = AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"}, content_hash="abc",
        )
        data = AgentObservationSerializer(obs).data
        assert data["observation_type"] == "page"
        assert data["data"] == {"url": "https://example.com"}
        assert data["content_hash"] == "abc"
        assert "id" in data
        assert "created_at" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentObservationSerializer -v`
Expected: FAIL — `ImportError: cannot import name 'AgentObservationSerializer'`

- [ ] **Step 3: Write AgentObservationSerializer**

Create `backend/apps/agent/serializers.py`:

```python
from __future__ import annotations

from rest_framework import serializers

from .models import AgentObservation


class AgentObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentObservation
        fields = (
            "id", "observation_type", "data", "artifact_refs",
            "content_hash", "redactions", "is_delta", "created_at",
        )
        read_only_fields = fields
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentObservationSerializer -v`
Expected: PASS

- [ ] **Step 5: Write tests for AgentActionSerializer with nested observations**

Add to `test_serializers.py`:

```python
from apps.agent.serializers import AgentActionSerializer


@pytest.mark.django_db
class TestAgentActionSerializer:
    def test_fields_and_nested_observations(self, create_action):
        from apps.agent.models import AgentObservation, ObservationType
        action = create_action(goal="test goal", reason="test reason")
        AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"},
        )
        data = AgentActionSerializer(action).data
        assert data["action_type"] == "observe_page"
        assert data["goal"] == "test goal"
        assert data["reason"] == "test reason"
        assert len(data["observations"]) == 1
        assert data["observations"][0]["observation_type"] == "page"
```

- [ ] **Step 6: Write AgentActionSerializer**

Append to `backend/apps/agent/serializers.py`:

```python
from .models import AgentAction


class AgentActionSerializer(serializers.ModelSerializer):
    observations = AgentObservationSerializer(many=True, read_only=True)

    class Meta:
        model = AgentAction
        fields = (
            "id", "action_type", "args_redacted", "goal", "reason",
            "hypothesis", "validation_status", "execution_status",
            "denial_reason", "executed_at", "created_at", "observations",
        )
        read_only_fields = fields
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentActionSerializer -v`
Expected: PASS

- [ ] **Step 8: Write tests for AgentTurnNoteSerializer and AgentNoteSerializer**

Add to `test_serializers.py`:

```python
from apps.agent.serializers import AgentNoteSerializer, AgentTurnNoteSerializer


@pytest.mark.django_db
class TestAgentNoteSerializer:
    def test_includes_turn_index(self, create_session):
        from apps.agent.models import AgentTurn, AgentNote, TurnStatus, NoteType
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=3, phase="recon", model="mock",
            status=TurnStatus.COMPLETED,
        )
        note = AgentNote.objects.create(
            session=session, turn=turn, note_type=NoteType.HYPOTHESIS,
            content={"text": "test hypothesis"},
        )
        data = AgentNoteSerializer(note).data
        assert data["turn_index"] == 3
        assert data["note_type"] == "hypothesis"
        assert data["content"] == {"text": "test hypothesis"}

    def test_turn_note_compact_shape(self, create_session):
        from apps.agent.models import AgentTurn, AgentNote, TurnStatus, NoteType
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=0, phase="recon", model="mock",
            status=TurnStatus.COMPLETED,
        )
        note = AgentNote.objects.create(
            session=session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/api/Users"},
        )
        data = AgentTurnNoteSerializer(note).data
        assert "turn_index" not in data
        assert data["note_type"] == "route"
```

- [ ] **Step 9: Write AgentNoteSerializer and AgentTurnNoteSerializer**

Append to `backend/apps/agent/serializers.py`:

```python
from .models import AgentNote


class AgentNoteSerializer(serializers.ModelSerializer):
    turn_index = serializers.IntegerField(source="turn.index", read_only=True)

    class Meta:
        model = AgentNote
        fields = (
            "id", "note_type", "content", "evidence_refs",
            "turn_index", "created_at",
        )
        read_only_fields = fields


class AgentTurnNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentNote
        fields = ("id", "note_type", "content", "evidence_refs", "created_at")
        read_only_fields = fields
```

- [ ] **Step 10: Run note serializer tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_serializers.py::TestAgentNoteSerializer -v`
Expected: PASS

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
