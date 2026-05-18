from django.contrib import admin

from .models import ScanTarget


@admin.register(ScanTarget)
class ScanTargetAdmin(admin.ModelAdmin):
    list_display = ("host", "base_url", "project", "status", "created_at")
    list_filter = ("status", "project")
    search_fields = ("host", "base_url", "ip")
    readonly_fields = ("id", "created_at", "updated_at")
