import logging
from datetime import date, datetime

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from users.permissions import IsHRRole

from .models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
    ReferenceSequence,
    SupportingDocument,
)
from .permissions import IsOwner
from .serializers import (
    FinancialYearSerializer,
    GradeEntitlementSerializer,
    LeaveApplicationSerializer,
    LeaveRuleSerializer,
    LeaveTypeSerializer,
    PublicHolidaySerializer,
    SupportingDocumentSerializer,
)
from .services import normalize_grade, resolve_grade_entitlement
from .services.storage import delete_document, upload_document
from .services.working_days import calculate_working_days

logger = logging.getLogger(__name__)


class GradeEntitlementViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for grade/entitlement rules (no hard delete)."""

    serializer_class = GradeEntitlementSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return GradeEntitlement.objects.all()

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        """Resolve a grade to the effective entitlement rule on a date."""
        grade = request.query_params.get("grade", "")
        key = normalize_grade(grade)
        if key is None:
            return Response(
                {"detail": "The grade query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        as_of = timezone.localdate()
        as_of_raw = request.query_params.get("as_of")
        if as_of_raw:
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                return Response(
                    {"detail": "The as_of parameter must be a valid date (YYYY-MM-DD)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        rule = resolve_grade_entitlement(key, as_of)
        return Response(
            {
                "grade": key,
                "days": rule.days if rule else None,
                "effective_from": rule.effective_from.isoformat() if rule else None,
            }
        )

class LeaveTypeViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for leave types (no hard delete)."""

    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return LeaveType.objects.all()


class LeaveRuleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for effective-dated leave rules (no hard delete)."""

    serializer_class = LeaveRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = LeaveRule.objects.all()
        leave_type = self.request.query_params.get("leave_type")
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)
        effective = self.request.query_params.get("effective")
        if effective == "current":
            queryset = queryset.filter(effective_from__lte=timezone.localdate())
        elif effective == "upcoming":
            queryset = queryset.filter(effective_from__gt=timezone.localdate())
        return queryset


class FinancialYearViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for configured financial-year periods (no hard delete)."""

    serializer_class = FinancialYearSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return FinancialYear.objects.all()


class PublicHolidayViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for configured public holidays (no hard delete)."""

    serializer_class = PublicHolidaySerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = PublicHoliday.objects.all()
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(date__year=year)
        return queryset


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = LeaveApplication.objects.filter(employee=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

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
            raise ValidationError("Submitted applications cannot be deleted.")
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
            raise ValidationError("Cannot upload documents to a submitted application.")

        file = self.request.FILES.get("file")
        if not file:
            raise ValidationError("No file provided.")

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
            raise ValidationError("Cannot remove documents from a submitted application.")
        try:
            delete_document(instance.file_path)
        except Exception:
            logger.exception("Failed to delete document %s from storage", instance.id)
        instance.delete()
