"""Liveness probe — extended to cover every backing service.

Shape: {"status": "ok", "db": <bool>, "redis": <bool>,
        "worker": <bool>, "version": <str>}

Each subsystem check is defensive — wrapped in try/except returning
a bool. The endpoint must never 500 on a broken dependency; the bools
indicate reality, and the top-level status stays "ok" so frontend's
top-bar connection pill can still render.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, JsonResponse
from redis import Redis


def _db_ok() -> bool:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() == (1,)
    except Exception:
        return False


def _redis_ok() -> bool:
    try:
        Redis.from_url(settings.REDIS_URL).ping()
        return True
    except Exception:
        return False


def _inspect_workers() -> dict[str, Any] | None:
    """Indirection so tests can mock `_inspect_workers` without touching
    Celery internals. Returns the dict reply from celery inspect.ping(),
    or None if no workers responded."""
    from config.celery import app

    return app.control.inspect(timeout=1.0).ping()


def _worker_ok() -> bool:
    try:
        return bool(_inspect_workers())
    except Exception:
        return False


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "status": "ok",
        "db": _db_ok(),
        "redis": _redis_ok(),
        "worker": _worker_ok(),
        "version": settings.APP_VERSION,
    })
