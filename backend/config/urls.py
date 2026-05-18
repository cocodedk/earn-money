"""Root URL configuration.

API routes are registered on a single DRF DefaultRouter under /api/.
Routers per app would be cleaner once the surface grows; for the
slice-1 contract one router is plenty.
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.projects.views import ProjectViewSet
from apps.targets.views import ScanTargetViewSet

from .health import health


router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"targets", ScanTargetViewSet, basename="target")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/", include(router.urls)),
]
