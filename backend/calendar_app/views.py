"""Calendar API views: read for all, writes for HR/superuser (§2, §3.7).

The working-day pattern exposes a single-row view (GET/PUT) so the landing page
can render a simple "toggle weekday" form rather than a list. Holidays and
events are list/create/retrieve/update with delete; financial years are the
shared ``leave.FinancialYear`` rows, so the calendar app exposes its own
viewset over them (same data, read for all, write for HR) to satisfy the
``/api/v1/calendar/financial-years/`` path the spec lists.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import mixins, permissions, response, status, viewsets
from rest_framework.views import APIView

from audit.models import AuditEntry
from audit.services import record_audit
from audit.validation import positive_int
from leave.models import FinancialYear
from leave.serializers import FinancialYearSerializer

from .models import CalendarEvent, Holiday, WorkingDayPattern
from .serializers import (
    CalendarEventSerializer,
    HolidaySerializer,
    WorkingDayPatternSerializer,
)
from .services import (
    can_access_calendar,
    get_holidays_for_range,
    get_working_day_pattern,
)

__all__ = [
    "CalendarEventViewSet",
    "FinancialYearViewSet",
    "HolidayViewSet",
    "IsCalendarAccess",
    "WorkingDaysView",
]


class IsCalendarAccess(permissions.BasePermission):
    """Read for any authenticated user, writes for HR/superuser (§2)."""

    message = "Only HR may change calendar configuration."

    def has_permission(self, request: Request, view) -> bool:
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return can_access_calendar(user)


class AuditedDestroyMixin:
    """Record a ``DELETED`` audit entry when a configuration row is removed."""

    def perform_destroy(self, instance):
        serializer = self.get_serializer(instance)
        target_type = serializer.target_type
        target_summary = serializer._audit_target_summary(instance)
        snapshot = serializer._audit_snapshot(instance)
        target_id = instance.pk

        super().perform_destroy(instance)

        actor = getattr(self.request, "user", None)
        if actor is None:
            return
        record_audit(
            actor=actor,
            action=AuditEntry.Action.DELETED,
            target_type=target_type,
            target_id=target_id,
            target_summary=target_summary,
            detail={"before": snapshot, "after": None},
        )


class FinancialYearViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    AuditedDestroyMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """List/create/update/delete financial years (§3.7).

    Read for any authenticated user. DELETE is refused with 409 while an
    entitlement or plan PROTECT-references the year (D3); an unreferenced year
    is removed and audited like any other configuration change.
    """

    serializer_class = FinancialYearSerializer
    permission_classes = [permissions.IsAuthenticated, IsCalendarAccess]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return FinancialYear.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return response.Response(
                {
                    "detail": (
                        "This financial year is referenced by leave entitlements "
                        "or plans and cannot be deleted."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return response.Response(status=status.HTTP_204_NO_CONTENT)


class HolidayViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    AuditedDestroyMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Raw rows for listing; resolved occurrences when ``start``/``end`` passed."""

    serializer_class = HolidaySerializer
    permission_classes = [permissions.IsAuthenticated, IsCalendarAccess]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Holiday.objects.all().select_related("financial_year")
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(date__year=positive_int(year, "year"))
        financial_year = self.request.query_params.get("financial_year")
        if financial_year:
            queryset = queryset.filter(financial_year_id=financial_year)
        return queryset

    def list(self, request, *args, **kwargs):
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start and end:
            try:
                start_d = date.fromisoformat(start)
                end_d = date.fromisoformat(end)
            except ValueError:
                return response.Response(
                    {"detail": "start and end must be ISO8601 dates."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if start_d > end_d:
                return response.Response(
                    {"detail": "start must be <= end."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved = get_holidays_for_range(start_d, end_d)
            data = [
                {
                    "date": item.date.isoformat(),
                    "name": item.holiday.name,
                    "is_recurring": item.holiday.is_recurring,
                    "observed_shift": item.holiday.observed_shift,
                    "holiday_id": item.holiday.pk,
                }
                for item in resolved
            ]
            # Paginate small sets by DRF pagination if configured; spec says
            # "returns resolved holiday dates in range" — return list as-is.
            return response.Response(data)
        return super().list(request, *args, **kwargs)


class CalendarEventViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    AuditedDestroyMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Events; can be filtered by a range (§3.7)."""

    serializer_class = CalendarEventSerializer
    permission_classes = [permissions.IsAuthenticated, IsCalendarAccess]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = CalendarEvent.objects.all()
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start and end:
            try:
                start_d = date.fromisoformat(start)
                end_d = date.fromisoformat(end)
            except ValueError:
                return queryset.none()
            queryset = queryset.filter(
                start_date__lte=end_d, end_date__gte=start_d
            )
        elif start:
            try:
                start_d = date.fromisoformat(start)
            except ValueError:
                return queryset.none()
            queryset = queryset.filter(end_date__gte=start_d)
        elif end:
            try:
                end_d = date.fromisoformat(end)
            except ValueError:
                return queryset.none()
            queryset = queryset.filter(start_date__lte=end_d)
        return queryset


class WorkingDaysView(APIView):
    """The single institution-wide working-day pattern (§3.4).

    GET reads it (defaults when HR has never saved one); PATCH replaces it. The
    pattern is a single row, so it is a plain API view rather than a viewset.
    """

    permission_classes = [permissions.IsAuthenticated, IsCalendarAccess]

    def get(self, request):
        # An unsaved row carries the model defaults, so GET reports Mon–Fri
        # without creating a row until HR actually saves a pattern.
        pattern = get_working_day_pattern() or WorkingDayPattern()
        serializer = WorkingDayPatternSerializer(
            instance=pattern, context={"request": request}
        )
        return response.Response(serializer.data)

    @transaction.atomic
    def patch(self, request):
        pattern = get_working_day_pattern()
        serializer = WorkingDayPatternSerializer(
            instance=pattern,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data)
