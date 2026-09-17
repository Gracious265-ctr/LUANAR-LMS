import logging
from datetime import datetime

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import LeaveApplication, ReferenceSequence, SupportingDocument
from .permissions import IsOwner
from .serializers import LeaveApplicationSerializer, SupportingDocumentSerializer
from .services.storage import delete_document, upload_document
from .services.working_days import calculate_working_days

logger = logging.getLogger(__name__)


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return LeaveApplication.objects.filter(employee=self.request.user)

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user, status=LeaveApplication.Status.DRAFT)
        instance = serializer.instance
        if instance.start_date and instance.end_date:
            instance.calculated_days = calculate_working_days(
                instance.start_date, instance.end_date
            )
            instance.save(update_fields=["calculated_days"])

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.start_date and instance.end_date:
            instance.calculated_days = calculate_working_days(
                instance.start_date, instance.end_date
            )
            instance.save(update_fields=["calculated_days"])

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != LeaveApplication.Status.DRAFT:
            return Response(
                {"detail": "Submitted applications cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != LeaveApplication.Status.DRAFT:
            return Response(
                {"detail": "Submitted applications cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.status != LeaveApplication.Status.DRAFT:
            raise PermissionDenied("Submitted applications cannot be deleted.")
        for doc in instance.documents.all():
            try:
                delete_document(doc.file_path)
            except Exception:
                logger.exception("Failed to delete document %s from storage", doc.id)
        instance.delete()

    @action(detail=False, methods=["post"], url_path="preview-days")
    def preview_days(self, request):
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        if not start_date or not end_date:
            return Response(
                {"detail": "start_date and end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        days = calculate_working_days(start, end)
        return Response({"days": days})

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        instance = self.get_object()
        if instance.status == LeaveApplication.Status.SUBMITTED:
            return Response(
                {"detail": "Application has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        missing_fields = []
        if not instance.leave_type_id:
            missing_fields.append("leave_type_id")
        if not instance.start_date:
            missing_fields.append("start_date")
        if not instance.end_date:
            missing_fields.append("end_date")
        if not instance.reason:
            missing_fields.append("reason")
        if missing_fields:
            return Response(
                {
                    "detail": "The following fields are required for submission: "
                    + ", ".join(missing_fields)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            year = timezone.now().year
            seq, _created = ReferenceSequence.objects.select_for_update().get_or_create(
                year=year, defaults={"last_number": 0}
            )
            seq.last_number = F("last_number") + 1
            seq.save(update_fields=["last_number"])
            seq.refresh_from_db()
            reference_number = f"LUANAR-{year}-{seq.last_number:05d}"

            instance.reference_number = reference_number
            instance.status = LeaveApplication.Status.SUBMITTED
            instance.submitted_at = timezone.now()
            if instance.start_date and instance.end_date:
                instance.calculated_days = calculate_working_days(
                    instance.start_date, instance.end_date
                )
            instance.save(
                update_fields=[
                    "reference_number",
                    "status",
                    "submitted_at",
                    "calculated_days",
                ]
            )

        return Response(
            {
                "detail": "Application submitted successfully.",
                "reference_number": reference_number,
            }
        )


class SupportingDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = SupportingDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return SupportingDocument.objects.filter(
            application__employee=self.request.user,
            application_id=self.kwargs["application_pk"],
        )

    def perform_create(self, serializer):
        application = LeaveApplication.objects.get(
            id=self.kwargs["application_pk"], employee=self.request.user
        )
        if application.status != LeaveApplication.Status.DRAFT:
            raise PermissionDenied("Cannot upload documents to a submitted application.")

        file = self.request.FILES.get("file")
        if not file:
            raise PermissionDenied("No file provided.")

        result = upload_document(file, str(application.id))
        serializer.save(
            application=application,
            file_path=result["path"],
            file_url=result["url"],
            file_name=file.name,
            file_size=file.size,
            content_type=file.content_type or "application/octet-stream",
        )

    def perform_destroy(self, instance):
        if instance.application.status != LeaveApplication.Status.DRAFT:
            raise PermissionDenied("Cannot remove documents from a submitted application.")
        try:
            delete_document(instance.file_path)
        except Exception:
            logger.exception("Failed to delete document %s from storage", instance.id)
        instance.delete()
