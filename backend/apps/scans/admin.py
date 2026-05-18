from django.contrib import admin

from .models import ScanRun, ScanTargetRun


@admin.register(ScanRun)
class ScanRunAdmin(admin.ModelAdmin):
    list_display = ("stub_slug", "project", "status", "started_at", "finished_at")
    list_filter = ("status", "stub_slug")
    search_fields = ("stub_slug", "project__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ScanTargetRun)
class ScanTargetRunAdmin(admin.ModelAdmin):
    list_display = ("target", "scan_run", "status", "started_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")
