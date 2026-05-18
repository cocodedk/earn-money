"""Minimal health endpoint.

Returns 200 with {"status": "ok"} as soon as Django boots. Used by:
- compose-up smoke test (curl http://localhost/api/health/)
- frontend's first page (proves the API is reachable through nginx)

When the platform grows real apps, this stays — it's the cheapest
liveness signal available.
"""
from __future__ import annotations

from django.db import connection
from django.http import JsonResponse, HttpRequest


def health(_request: HttpRequest) -> JsonResponse:
    db_ok = False
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            db_ok = cur.fetchone() == (1,)
    except Exception:  # pragma: no cover — DB unreachable
        db_ok = False
    return JsonResponse({"status": "ok", "db": db_ok})
