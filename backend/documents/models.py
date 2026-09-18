from django.db import models


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