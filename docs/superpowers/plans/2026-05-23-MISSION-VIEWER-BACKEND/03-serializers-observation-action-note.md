---
tier: CAPABLE
depends_on: []
files:
  creates:
    - backend/apps/agent/serializers.py
    - backend/apps/agent/tests/test_serializers.py
  modifies: []
  deletes: []
  renames: []
  generated: []
exports:
  - name: AgentObservationSerializer
    file: backend/apps/agent/serializers.py
  - name: AgentActionSerializer
    file: backend/apps/agent/serializers.py
  - name: AgentNoteSerializer
    file: backend/apps/agent/serializers.py
  - name: AgentTurnNoteSerializer
    file: backend/apps/agent/serializers.py
imports: []
allow_extra_files: false
---

# Task 3A: Serializers — Observation, Action, Note

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

Continues in [03-serializers-turn-session.md](03-serializers-turn-session.md).
