from django.db import models


class ApprovedLeaveDocument(models.Model):
    """The official approved-leave document PDF for one application (Unit 23).

    Exactly one document per application: a later finalisation of the same
    application replaces the stored file and refreshes this row, it never
    creates a second row. The PDF bytes live in the Unit 19 storage backend
    (never in the database); this row is the metadata + access key.
    """

    application = models.OneToOneField(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="approved_leave_document",
    )
    file_path = models.CharField(max_length=512)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        ref = self.application.reference_number or self.application_id
        return f"ApprovedLeaveDocument({ref} - {self.file_name})"


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