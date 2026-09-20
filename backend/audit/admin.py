from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    """View-only inspector for the append-only audit log."""

    list_display = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "target_summary",
        "created_at",
    )
    list_filter = ("action", "target_type")
    search_fields = (
        "actor__first_name",
        "actor__last_name",
        "actor__email",
        "target_summary",
        "target_id",
    )
    raw_id_fields = ("actor",)
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "target_summary",
        "detail",
        "reason",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_delete_permission(self, request, obj=None):
        return False