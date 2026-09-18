from datetime import date

from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsHRRole

from .models import (
    FinancialYear,
    GradeEntitlement,
    LeaveRule,
    LeaveType,
    PublicHoliday,
)
from .serializers import (
    FinancialYearSerializer,
    GradeEntitlementSerializer,
    LeaveRuleSerializer,
    LeaveTypeSerializer,
    PublicHolidaySerializer,
)
from .services import normalize_grade, resolve_grade_entitlement


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
