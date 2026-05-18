from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "type", "level", "subject_type", "scan_run")
    list_filter = ("level", "type", "subject_type")
    search_fields = ("message", "type", "subject_type")
    readonly_fields = (
        "id",
        "created_at",
        "type",
        "scan_run",
        "target",
        "subject_type",
        "subject_id",
        "level",
        "message",
        "data",
    )

    def has_change_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only

    def has_delete_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only
