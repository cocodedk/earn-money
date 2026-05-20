"""Finding serializers.

Read serializer (everything read-only) is used by the list + retrieve
endpoints. The narrow `FindingStatusSerializer` powers the
operator-triage PATCH /api/findings/<id>/status/ action.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Finding, FindingStatus


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = (
            "id",
            "scan_run",
            "target",
            "stub_slug",
            "title",
            "category",
            "severity",
            "confidence",
            "status",
            "data",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class FindingStatusSerializer(serializers.Serializer):
    """Narrow write serializer for the status triage endpoint.

    Other fields in the request body are silently dropped — only
    `status` is honoured. Invalid values return 400 with the field
    error map (matches the API-error contract negotiated with the
    frontend agent).
    """

    status = serializers.ChoiceField(choices=FindingStatus.choices)
