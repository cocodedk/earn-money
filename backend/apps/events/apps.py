"""Events app — unified audit / SSE event log.

See [[project-event-log-medium-done-well]] in memory for the contract.
"""
from __future__ import annotations

from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    label = "events"
