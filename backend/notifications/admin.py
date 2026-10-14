"""Read-only inspector for the notification outbox.

The outbox is an append-only delivery ledger, so admin cannot be a management
surface: it exists so HR and support can answer "did the mail go out, to whom,
and if not, why?" without a shell. It deliberately exposes no add/change/delete
permission — rows move ``pending → sent|failed`` only through the delivery task.
"""

from django.contrib import admin

<<<<<<< HEAD
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "email_to",
        "recipient",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("email_to", "subject")
    readonly_fields = (
        "event_type",
        "recipient",
        "channel",
        "email_to",
        "subject",
        "body",
        "status",
        "attempts",
        "error",
        "application_id",
        "target_object_id",
        "created_at",
        "sent_at",
    )
=======
from .models import NotificationOutbox


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    """View-only inspector: the delivery record is written by the task, not by hand."""

    readonly_fields = (
        "kind",
        "role_label",
        "recipient_email",
        "subject",
        "state",
        "error",
        "created_at",
        "sent_at",
        "body",
        "application",
        "delegation",
        "reassignment",
        "plan",
        "plan_block",
        "cancellation",
        "submission_cycle",
    )
    list_display = (
        "created_at",
        "kind",
        "role_label",
        "recipient_email",
        "state",
    )
    list_filter = ("state", "kind", "role_label", "created_at")
    search_fields = ("recipient_email", "subject", "body", "error")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
>>>>>>> feature/plans-teams
