"""ScanTarget serializer.

UniqueTogetherValidator is wired explicitly because the model's
UniqueConstraint isn't auto-detected by DRF (only the older
`unique_together` Meta is). Without this, a duplicate (project,
base_url) would propagate as an IntegrityError → 500.

Per spec docs/superpowers/specs/2026-05-18-MVP-GUI/03-targets.md
the Add-target form lists `host optional` and `ip optional`; only
`project` and `base_url` are required. host falls back to the
base_url's netloc (port stripped) so the stored row always carries
a meaningful host for downstream runner code (SSL/SNI, logging).
"""
from __future__ import annotations

from urllib.parse import urlsplit

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import ScanTarget


class ScanTargetSerializer(serializers.ModelSerializer):
    host = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=253,
    )
    ip = serializers.IPAddressField(
        required=False, allow_blank=True, allow_null=True,
    )

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

    def validate(self, attrs: dict) -> dict:
        # Spec §Validation: host/ip are optional but the model stores
        # a non-null host. Derive it from base_url when missing/blank
        # so downstream code can rely on `target.host`.
        if not attrs.get("host") and attrs.get("base_url"):
            attrs["host"] = urlsplit(attrs["base_url"]).hostname or ""
        # ip is nullable at the model layer — normalise blank strings
        # to None so the DB carries NULL, not "".
        if not attrs.get("ip"):
            attrs["ip"] = None
        return attrs
