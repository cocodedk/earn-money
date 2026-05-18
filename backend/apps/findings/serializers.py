"""Finding read-only serializer.

Status flips (PATCH /<id>/status/) land as a separate @action in a
follow-up task once the operator-triage UI is built.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Finding


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
