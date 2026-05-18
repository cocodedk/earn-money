"""Project serializer.

`target_count` and `scan_run_count` come from queryset annotations on
the viewset — denormalized to avoid N+1 (agreed with frontend agent,
2026-05-18). Timestamps are DRF's default ISO-8601 UTC.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    target_count = serializers.IntegerField(read_only=True)
    scan_run_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "description",
            "target_count",
            "scan_run_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
