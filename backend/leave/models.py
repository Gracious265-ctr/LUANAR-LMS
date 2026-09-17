import uuid

from django.conf import settings
from django.db import models


class LeaveApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_applications",
    )

    # Soft reference — no FK until Unit 4 ships a real LeaveType model.
    # TODO(unit-4): replace with FK to LeaveType once available;
    # add migration to validate existing rows.
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    calculated_days = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    reference_number = models.CharField(
        max_length=32, unique=True, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        ref = self.reference_number or "Draft"
        return f"LeaveApplication({ref} - {self.employee})"


class SupportingDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_path = models.CharField(max_length=512)
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"Document({self.file_name})"


class ReferenceSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"RefSeq({self.year}: {self.last_number})"
