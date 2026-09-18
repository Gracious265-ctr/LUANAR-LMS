"""Read-only inspector for the single official leave-document template.

The HR application UI is the management surface (it validates the field
catalog); admin exists only to inspect the stored configuration.
"""

from django.contrib import admin

from .models import LeaveDocumentTemplate


@admin.register(LeaveDocumentTemplate)
class LeaveDocumentTemplateAdmin(admin.ModelAdmin):
    """View-only inspector: never add, edit, or delete the template singleton."""

    readonly_fields = (
        "title",
        "header",
        "intro",
        "closing",
        "footer",
        "fields",
        "signature_areas",
        "created_at",
        "updated_at",
    )
    list_display = ("title", "updated_at")
    ordering = ("-updated_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False