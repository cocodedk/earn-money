"""ScanTarget serializer.

UniqueTogetherValidator is wired explicitly because the model's
UniqueConstraint isn't auto-detected by DRF (only the older
`unique_together` Meta is). Without this, a duplicate (project,
base_url) would propagate as an IntegrityError → 500.
"""
from __future__ import annotations

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import ScanTarget


class ScanTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanTarget
        fields = (
            "id",
            "project",
            "base_url",
            "host",
            "ip",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        validators = [
            UniqueTogetherValidator(
                queryset=ScanTarget.objects.all(),
                fields=("project", "base_url"),
                message="A target with this project and base_url already exists.",
            ),
        ]
