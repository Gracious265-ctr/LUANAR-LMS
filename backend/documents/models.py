from django.db import models
from django.db.models import Q


class ApprovedLeaveDocumentLockedError(Exception):
    """Raised on an attempt to mutate a finalized approved document."""


class ApprovedLeaveDocumentQuerySet(models.QuerySet):
    """Sealed once ``ready``: no queryset-wide update/delete of a final PDF."""

    def delete(self):
        if self.filter(status=ApprovedLeaveDocument.Status.READY).exists():
            raise ApprovedLeaveDocumentLockedError(
                "A generated approved document cannot be deleted."
            )
        return super().delete()


class ApprovedLeaveDocumentManager(
    models.Manager.from_queryset(ApprovedLeaveDocumentQuerySet)
):
    """Manager enforcing that a ``ready`` document is never rewritten."""


class LeaveDocumentTemplate(models.Model):
    """The single official approved-leave document template.

    A configuration singleton: HR edits official wording, the label/inclusion/
    order of the fixed data-field catalog, and signature captions. Values are
    never stored here — the approved application record is the data source when
    Unit 23 renders real documents.
    """

    title = models.CharField(
        max_length=200,
        help_text="The document title, e.g. APPROVED LEAVE.",
    )
    header = models.TextField(
        blank=True,
        help_text="Page/branding header text (university or office name).",
    )
    intro = models.TextField(
        blank=True,
        help_text="Official opening wording shown before the data fields.",
    )
    fields = models.JSONField(
        default=list,
        help_text='Ordered list of {"key", "label"} rows drawn from the field catalog.',
    )
    closing = models.TextField(
        blank=True,
        help_text="Official closing wording shown after the data fields.",
    )
    signature_areas = models.JSONField(
        default=list,
        help_text='Ordered list of {"label"} signature captions.',
    )
    footer = models.TextField(
        blank=True,
        help_text="Footer text shown at the bottom of the document.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class ApprovedLeaveDocument(models.Model):
    """The generated official document for one approved application (Unit 23b).

    Exactly one row per application, created ``pending`` inside the approval
    transaction by :func:`leave.services.finalise.finalise_approved_application`
    and flipped to ``ready`` (or ``failed``) by the ``render_approved_document``
    task on commit. The row is the idempotency anchor: re-finalising resolves the
    same row rather than generating a second document.

    The document is a **retryable derived artifact**, not business state — the
    balance deduction is transactional and is not affected if a render fails. Once
    ``ready`` the file fields and status are immutable, so the artifact of what
    was approved on a given date cannot later be rewritten.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    application = models.OneToOneField(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="approved_document",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Storage path under the approved/{application_id}/ prefix.",
    )
    file_url = models.URLField(
        max_length=1000,
        blank=True,
        default="",
        help_text="Cached signed URL; a fresh one is minted per read.",
    )
    file_name = models.CharField(max_length=255, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True, default="")
    approved_on = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the application reached its final approval.",
    )
    rendered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Sanitized failure summary; never a traceback.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ApprovedLeaveDocumentManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    # A ready document always has a stored file; a pending or
                    # failed one never does.
                    Q(status="ready", file_path__gt="")
                    | Q(status__in=["pending", "failed"], file_path="")
                ),
                name="approved_document_state_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_status_display()} document for {self.application_id}"

    @property
    def is_available(self) -> bool:
        """True when a signed URL may be minted for this document."""
        return self.status == self.Status.READY and bool(self.file_path)

    def mark_ready(self, **file_fields) -> None:
        """Record a successful render. The only mutation a ``ready`` row refuses."""
        if self.status == self.Status.READY:
            raise ApprovedLeaveDocumentLockedError(
                "This approved document has already been generated."
            )
        for name, value in file_fields.items():
            setattr(self, name, value)
        self.status = self.Status.READY
        self.error_message = ""
        self.save()

    def mark_failed(self, message: str) -> None:
        """Record a render failure without leaking internals to readers."""
        if self.status == self.Status.READY:
            raise ApprovedLeaveDocumentLockedError(
                "A generated approved document cannot be marked failed."
            )
        self.status = self.Status.FAILED
        self.error_message = _sanitize_error(message)
        self.save()

    def save(self, *args: object, **kwargs: object) -> None:
        """Refuse to change a sealed field once the row is ``ready`` in the database.

        The guard deliberately compares against the **persisted** state rather
        than the in-memory one: ``mark_ready`` assigns ``status = READY``
        before saving, so a guard reading the instance's own status would
        reject the very transition that publishes the document.
        """
        if not self._state.adding:
            sealed = self._sealed_values()
            persisted = (
                type(self).objects.filter(pk=self.pk).values(*sealed).first()
            )
            if persisted is not None and persisted.get("status") == self.Status.READY:
                changed = sorted(
                    name
                    for name, attname in sealed.items()
                    if getattr(self, attname) != persisted.get(name)
                )
                if changed:
                    raise ApprovedLeaveDocumentLockedError(
                        "A generated approved document is immutable; refused to "
                        f"change: {', '.join(changed)}."
                    )
        super().save(*args, **kwargs)

    def _sealed_values(self) -> dict[str, str]:
        """``{field name: attname}`` for each sealed field, so FKs compare by id.

        ``application`` is a relation, so its value is compared as
        ``application_id``; comparing the related object would report a change
        on every save even when nothing moved.
        """
        sealed: dict[str, str] = {}
        for field in self._meta.get_fields():
            if field.name in SEALED_FIELDS:
                sealed[field.name] = getattr(field, "attname", field.name)
        return sealed

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ApprovedLeaveDocumentLockedError(
            "Approved documents are never deleted."
        )


#: Fields a ``ready`` document may never change after the first write.
SEALED_FIELDS = frozenset(
    {
        "application",
        "status",
        "file_path",
        "file_url",
        "file_name",
        "file_size",
        "content_type",
        "rendered_at",
    }
)


def _sanitize_error(message: str) -> str:
    """Reduce an exception message to a single safe line for API readers.

    The render task logs the full traceback server-side; what lands in the row is
    what an employee or HR may read, so it must not carry file paths, SQL or
    stack frames.
    """
    first_line = str(message or "").strip().splitlines()[0] if str(message) else ""
    return first_line[:500]
