"""Event read-only serializer.

Events stream to the frontend via SSE; for the REST read path the
JSON shape stays identical so the frontend's event-handler can consume
both without branching.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            "id",
            "type",
            "scan_run",
            "target",
            "subject_type",
            "subject_id",
            "level",
            "message",
            "data",
            "created_at",
        )
        read_only_fields = fields
