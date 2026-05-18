"""FindingViewSet — read-only list/retrieve over Finding rows.

Filters on list:
  ?scan_run=<uuid>    scope to one run
  ?status=<value>     candidate | confirmed | rejected | stale
  ?stub_slug=<slug>   e.g. "1.1"

PATCH /<id>/status/ for operator triage will land as a follow-up.
"""
from __future__ import annotations

from rest_framework import viewsets

from .models import Finding
from .serializers import FindingSerializer


class FindingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FindingSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = Finding.objects.all().order_by("-created_at")
        params = self.request.query_params
        if params.get("scan_run"):
            qs = qs.filter(scan_run_id=params["scan_run"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("stub_slug"):
            qs = qs.filter(stub_slug=params["stub_slug"])
        return qs
