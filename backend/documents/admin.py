"""Read-only inspector for the single official leave-document template and the
generated approved-leave documents. The HR application UI is the management
surface (it validates the field catalog); admin exists only to inspect the
stored configuration and generated files.
"""

from django.contrib import admin

from .models import ApprovedLeaveDocument, LeaveDocumentTemplate


@admin.register(ApprovedLeaveDocument)
class ApprovedLeaveDocumentAdmin(admin.ModelAdmin):
    """View-only inspector for generated approved-leave documents."""

    readonly_fields = (
        "application",
        "file_path",
        "file_name",
        "file_size",
        "content_type",
        "generated_at",
    )
    list_display = ("application", "file_name", "file_size", "generated_at")
    ordering = ("-generated_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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