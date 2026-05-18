"""Evidence read-only serializer.

Evidence rows are append-only at the model layer; the API surface is
list + retrieve only — no write endpoints.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Evidence


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = (
            "id",
            "scan_run",
            "target",
            "finding",
            "source",
            "url",
            "method",
            "field",
            "matched_value",
            "raw_excerpt",
            "content_hash",
            "data",
            "created_at",
        )
        read_only_fields = fields
