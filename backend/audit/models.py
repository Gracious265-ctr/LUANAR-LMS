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
        CORRECTION_REQUESTED = "correction_requested", "Returned for correction"
        APPLICATION_RESUBMITTED = "application_resubmitted", "Application resubmitted"
        DOCUMENT_ADDED = "document_added", "Document added"
        DOCUMENT_REPLACED = "document_replaced", "Document replaced"
        DOCUMENT_REMOVED = "document_removed", "Document removed"
        CANCELLATION_REQUESTED = "cancellation_requested", "Cancellation requested"
        CANCELLATION_WITHDRAWN = "cancellation_withdrawn", "Application withdrawn"
        CANCELLATION_STAGE_APPROVED = (
            "cancellation_stage_approved",
            "Cancellation stage approved",
        )
        CANCELLATION_APPROVED = "cancellation_approved", "Cancellation approved"
        CANCELLATION_REJECTED = "cancellation_rejected", "Cancellation rejected"
        BALANCE_RESTORED = "balance_restored", "Leave balance restored"

    class TargetType(models.TextChoices):
        """The authoritative set of audit ``target_type`` codes."""

        RECORD = "record", "Record"
        ENTITLEMENT = "entitlement", "Entitlement"
        LEAVE_TYPE = "leavetype", "Leave type"
        LEAVE_RULE = "leaverule", "Leave rule"
        FINANCIAL_YEAR = "financialyear", "Financial year"
        PUBLIC_HOLIDAY = "publicholiday", "Public holiday"
        WORKFLOW = "workflow", "Workflow"
        EMPLOYEE = "employee", "Employee"
        APPLICATION = "application", "Application"
        DELEGATION = "delegation", "Delegation"
        REASSIGNMENT = "reassignment", "Reassignment"
        DOCUMENT_TEMPLATE = "document-template", "Document template"
        CANCELLATION = "cancellation", "Cancellation request"
        BALANCE_TRANSACTION = "balance_transaction", "Leave balance transaction"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_entries",
        help_text="The user who performed the action.",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(
        max_length=32,
        choices=TargetType.choices,
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