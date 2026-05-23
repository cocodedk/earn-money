from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import AgentSession
from .serializers import (
    AgentNoteSerializer,
    AgentSessionSerializer,
    AgentTurnSerializer,
)


class AgentSessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AgentSessionSerializer

    def get_queryset(self):
        qs = AgentSession.objects.select_related(
            "target", "scan_run", "scan_target_run",
        ).order_by("-created_at")
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("target"):
            qs = qs.filter(target_id=params["target"])
        return qs

    @action(detail=True, methods=["get"])
    def turns(self, _request: Request, pk=None) -> Response:
        session = self.get_object()
        qs = session.turns.prefetch_related(
            "actions__observations", "notes",
        ).order_by("index")
        page = self.paginate_queryset(qs)
        serializer = AgentTurnSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def notes(self, _request: Request, pk=None) -> Response:
        session = self.get_object()
        qs = session.notes.select_related("turn").order_by("created_at")
        page = self.paginate_queryset(qs)
        serializer = AgentNoteSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
