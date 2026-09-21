from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """One entry in the authoritative audit/history log.

    Records who changed which target record when, the changed before/after
    values for configuration and state changes, and any relevant decision or
    reassignment reason. Entries are append-only and HR-read-only; they are
    written through :func:`audit.services.record_audit` from the same code that
    owns each action so a failed action never leaves a phantom entry.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        REASSIGNED = "reassigned", "Reassigned"
        SUBMITTED = "submitted", "Submitted"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_entries",
        help_text="The user who performed the action.",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    target_type = models.CharField(
        max_length=32,
        help_text="The type of record changed, e.g. entitlement or application.",
    )
    target_id = models.CharField(
        max_length=64,
        help_text="The polymorphic primary key of the target record.",
    )
    target_summary = models.CharField(
        max_length=255,
        help_text="A human-readable description of the changed record.",
    )
    detail = models.JSONField(
        null=True,
        blank=True,
        help_text='Optional {"before": {...}, "after": {...}} of the changed fields.',
    )
    reason = models.TextField(
        blank=True,
        default="",
        help_text="Optional reason recorded for decisions and reassignments.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="auditentry_target_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.target_type} {self.target_id}"