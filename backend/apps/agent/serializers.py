from __future__ import annotations

from rest_framework import serializers

from .models import (
    AgentAction,
    AgentNote,
    AgentObservation,
    AgentPhase,
    AgentSession,
    AgentTurn,
)


class AgentObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentObservation
        fields = (
            "id", "observation_type", "data", "artifact_refs",
            "content_hash", "redactions", "is_delta", "created_at",
        )
        read_only_fields = fields


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
