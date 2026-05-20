"""Celery application factory.

Reads broker/backend from Django settings; tasks are auto-discovered
from any INSTALLED_APP that has a `tasks.py` module. No tasks ship in
this initial scaffold — the worker boots, claims the broker, and waits.
"""
from __future__ import annotations

import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Use Django settings, prefixed with `CELERY_`.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self) -> None:
    """Sanity check — celery -A config inspect ping."""
    print(f"Request: {self.request!r}")
