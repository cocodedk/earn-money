from django.contrib import admin

from .models import Evidence


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "field", "target", "scan_run")
    list_filter = ("source",)
    search_fields = ("matched_value", "raw_excerpt", "url", "field")
    readonly_fields = (
        "id",
        "created_at",
        "scan_run",
        "target",
        "finding",
        "source",
        "url",
        "method",
        "field",
        "matched_value",
        "raw_excerpt",
        "content_hash",
        "data",
    )

    def has_change_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only

    def has_delete_permission(self, *_args: object, **_kwargs: object) -> bool:
        return False  # append-only
