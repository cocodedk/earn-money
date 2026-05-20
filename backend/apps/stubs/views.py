"""Stubs ViewSet — read-only list + retrieve over the cookbook tree.

GET /api/stubs/             → list (no body, no pagination — 278 items
                              fit comfortably; frontend filters client-
                              side)
GET /api/stubs/<phase.spec>/ → detail (includes `body` markdown)
"""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from .registry import get_registry


class StubViewSet(viewsets.ViewSet):
    # Allow dots in the URL `pk` ("1.1", "24.9") — DRF's default
    # pattern excludes them.
    lookup_value_regex = r"\d+\.\d+"
    pagination_class = None

    def list(self, request: Request) -> Response:
        registry = get_registry()
        rows = [
            {k: v for k, v in stub.items() if k != "body"}
            for stub in registry.all()
        ]
        return Response(rows)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        stub = get_registry().get(pk or "")
        if stub is None:
            raise NotFound("No stub with that slug.")
        return Response(stub)
