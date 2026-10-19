import logging
from datetime import date, datetime

from django.db.models import Prefetch
from django.http import Http404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from audit.validation import positive_int

from users.permissions import IsHRRole

from ..models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
    SupportingDocument,
)
from ..permissions import IsOwner
from ..serializers import (
    EmployeeLeaveTypeSerializer,
    FinancialYearSerializer,
    GradeEntitlementSerializer,
    LeaveApplicationSerializer,
    LeaveRuleSerializer,
    LeaveTypeSerializer,
    PublicHolidaySerializer,
)
from ..services import (
    leave_types_available_to,
    normalize_grade,
    resolve_grade_entitlement,
)
from ..services.storage import delete_document
from ..services.working_days import calculate_working_days, holidays_in_range
from .documents import SupportingDocumentFeedView, SupportingDocumentViewSet

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
        return GradeEntitlement.objects.all().select_related("leave_type")

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


class EmployeeLeaveTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Employee-facing, read-only catalog of leave types.

    A type is offered only if it is active and there is an effective
    ``GradeEntitlement`` for the viewer's grade. That is the "configured and
    available now" rule — a scheduled entitlement does not make it appear, and
    an unmapped grade sees an empty list.
    """

    serializer_class = EmployeeLeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        profile = getattr(self.request.user, "employee_profile", None)
        grade = getattr(profile, "grade", None) if profile else None
        return leave_types_available_to(grade)


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
            queryset = queryset.filter(
                leave_type=positive_int(leave_type, "leave_type")
            )
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
            queryset = queryset.filter(
                date__year=positive_int(year, "year")
            )
        return queryset


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = LeaveApplication.objects.filter(
            employee=self.request.user
        ).prefetch_related(
            Prefetch(
                "documents",
                queryset=SupportingDocument.objects.filter(
                    status=SupportingDocument.Status.ACTIVE
                ),
                to_attr="active_documents",
            )
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        # `My Applications` hides saved drafts so they only surface on the
        # dedicated Drafts view; `exclude_status` accepts a comma-separated list.
        exclude_status = self.request.query_params.get("exclude_status")
        if exclude_status:
            excluded = [s.strip() for s in exclude_status.split(",") if s.strip()]
            if excluded:
                qs = qs.exclude(status__in=excluded)
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

    #: Statuses an employee may still edit (Unit 25 D7). ``REJECTED`` is
    #: editable because the applicant may choose to rework a rejected
    #: application and resubmit it; ``resubmit`` then re-validates, advances
    #: ``submission_cycle`` and freezes a new revision.
    EDITABLE_STATUSES = (
        LeaveApplication.Status.DRAFT,
        LeaveApplication.Status.REJECTED,
    )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in self.EDITABLE_STATUSES:
            return Response(
                {"detail": "This application cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in self.EDITABLE_STATUSES:
            return Response(
                {"detail": "This application cannot be edited."},
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
        # Weekends and configured public holidays are excluded; the count says
        # how many public holidays were dropped so the UI can explain the number.
        holidays = holidays_in_range(start, end) if start <= end else {}
        return Response({"days": days, "holidays_excluded": len(holidays)})
