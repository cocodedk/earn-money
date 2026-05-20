from django.contrib import admin

from .models import Finding


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ("title", "stub_slug", "target", "status", "severity", "confidence")
    list_filter = ("status", "severity", "confidence", "stub_slug")
    search_fields = ("title", "stub_slug", "category")
    readonly_fields = ("id", "created_at", "updated_at")
