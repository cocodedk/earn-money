"""Django project package.

Imports the Celery app so the @shared_task decorator works as soon as
Django starts. Pattern: https://docs.celeryq.dev/en/stable/django/
"""
from __future__ import annotations

from .celery import app as celery_app

__all__ = ("celery_app",)
