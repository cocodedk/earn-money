"""ScanRun serializer.

Create payload: project + stub_slug + target_ids (write-only). Validates
that stub_slug refers to a real cookbook stub and every target_id
belongs to the named project. On success, creates the ScanRun and one
ScanTargetRun per target.

Read response: scan-run fields + denormalized `target_run_count`
(annotated on the queryset in the viewset).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.stubs.registry import get_registry
from apps.targets.models import ScanTarget

from .models import ScanRun, ScanTargetRun


class ScanRunSerializer(serializers.ModelSerializer):
    target_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        min_length=1,
    )
    target_run_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ScanRun
        fields = (
            "id",
            "project",
            "stub_slug",
            "status",
            "started_at",
            "finished_at",
            "target_ids",
            "target_run_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "started_at",
            "finished_at",
            "target_run_count",
            "created_at",
            "updated_at",
        )

    def validate_stub_slug(self, value: str) -> str:
        if get_registry().get(value) is None:
            raise serializers.ValidationError(f"Unknown stub slug: {value}")
        return value

    def validate(self, attrs: dict) -> dict:
        project = attrs["project"]
        target_ids = attrs["target_ids"]
        targets = list(ScanTarget.objects.filter(id__in=target_ids, project=project))
        if len(targets) != len(set(target_ids)):
            raise serializers.ValidationError(
                {"target_ids": "All target_ids must belong to the project."}
            )
        attrs["_targets"] = targets
        return attrs

    def create(self, validated_data: dict) -> ScanRun:
        targets = validated_data.pop("_targets")
        validated_data.pop("target_ids")
        scan_run = ScanRun.objects.create(**validated_data)
        ScanTargetRun.objects.bulk_create(
            [ScanTargetRun(scan_run=scan_run, target=t) for t in targets]
        )
        return scan_run
