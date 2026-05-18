"""Root URL configuration.

Real app routes will land under /api/ as the apps/* modules come online.
For now the only endpoint is a health check that proves the stack is
wired correctly through nginx → backend.
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import path

from .health import health


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
]
