from django.contrib import admin

from .models import ScanEvent, ScanRun, ScanTargetRun


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


@admin.register(ScanEvent)
class ScanEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scan_run", "level", "event_type")
    list_filter = ("level", "event_type")
    search_fields = ("message", "event_type")
    readonly_fields = (
        "id",
        "created_at",
        "scan_run",
        "target",
        "level",
        "event_type",
        "message",
        "data",
    )

    def has_change_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only

    def has_delete_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only
