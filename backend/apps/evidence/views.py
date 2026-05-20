"""EvidenceViewSet — read-only list/retrieve.

Filters on list:
  ?scan_run=<uuid>    scope to one run
  ?target=<uuid>      scope to one target
  ?source=<value>     header | cookie | html | …
  ?finding=<uuid>     evidence linked to a specific finding
"""
from __future__ import annotations

from rest_framework import viewsets

from .models import Evidence
from .serializers import EvidenceSerializer


class EvidenceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EvidenceSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = Evidence.objects.all().order_by("-created_at")
        params = self.request.query_params
        if params.get("scan_run"):
            qs = qs.filter(scan_run_id=params["scan_run"])
        if params.get("target"):
            qs = qs.filter(target_id=params["target"])
        if params.get("source"):
            qs = qs.filter(source=params["source"])
        if params.get("finding"):
            qs = qs.filter(finding_id=params["finding"])
        return qs
