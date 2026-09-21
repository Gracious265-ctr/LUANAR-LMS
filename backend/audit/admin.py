from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "prev_state", "new_state")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "action")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "actor",
        "action",
        "content_type",
        "object_id",
        "prev_state",
        "new_state",
        "metadata",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False