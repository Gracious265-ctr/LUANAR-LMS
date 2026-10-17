"""Views for Leave Plans (refinement unit 04).

Owner endpoints (list/create/detail/delete/apply) are plain ``IsAuthenticated``:
a plan belongs to the person who made it, and ownership is enforced by scoping
every queryset to ``request.user``. The team calendar and scope-options endpoints
are the only ones that look sideways at anyone else, and both resolve their
allowed scopes through :func:`~plans.services.resolve_scopes` so the caller can
never widen their own visibility by crafting a token.
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from leave.models import FinancialYear

from .models import LeavePlan
from .serializers import (
    LeavePlanSerializer,
    LeavePlanWriteSerializer,
    PlanScopeSerializer,
)
from .services import (
    PlanError,
    convert_plan_to_draft,
    create_plan,
    find_scope,
    plans_for_scope,
    resolve_scopes,
    update_plan,
)


def _active_financial_year():
    return FinancialYear.objects.filter(is_active=True).order_by("-start_date").first()


class LeavePlanViewSet(ModelViewSet):
    """``/api/v1/plans/`` — a person's own plans, never anyone else's."""

    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return (
            LeavePlan.objects.filter(employee=self.request.user)
            .select_related("leave_type", "financial_year")
            .order_by("planned_start_date", "-created_at")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LeavePlanWriteSerializer
        return LeavePlanSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fy = serializer.validated_data.get("financial_year") or _active_financial_year()
        if fy is None:
            return Response(
                {"detail": "No financial year is configured yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            plan, warning = create_plan(
                employee=request.user,
                leave_type=serializer.validated_data["leave_type"],
                financial_year=fy,
                start_date=serializer.validated_data["planned_start_date"],
                end_date=serializer.validated_data["planned_end_date"],
                notes=serializer.validated_data.get("notes", ""),
            )
        except PlanError as exc:
            return Response({"leave_type": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            LeavePlanSerializer(plan).data | (
                {"overlap_warning": warning} if warning else {}
            ),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        fy = serializer.validated_data.get("financial_year") or _active_financial_year()
        if fy is None:
            return Response(
                {"detail": "No financial year is configured yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            plan, warning = update_plan(
                plan=instance,
                leave_type=serializer.validated_data.get(
                    "leave_type", instance.leave_type
                ),
                financial_year=fy,
                start_date=serializer.validated_data.get(
                    "planned_start_date", instance.planned_start_date
                ),
                end_date=serializer.validated_data.get(
                    "planned_end_date", instance.planned_end_date
                ),
                notes=serializer.validated_data.get("notes", instance.notes),
            )
        except PlanError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            LeavePlanSerializer(plan).data | (
                {"overlap_warning": warning} if warning else {}
            )
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Deleting is how "give up on this plan" is recorded for good; it is not
        # the same as cancelling (which keeps the row as history). Both are
        # allowed, and the frontend offers the one the user means.
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class PlanApplyView(APIView):
    """``POST /api/v1/plans/{id}/apply/`` — convert to a draft and hand back its id."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        plan = (
            LeavePlan.objects.filter(pk=pk, employee=request.user)
            .select_related("leave_type", "financial_year")
            .first()
        )
        if plan is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            application = convert_plan_to_draft(plan=plan)
        except PlanError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"application_id": application.pk})


class PlanScopeOptionsView(APIView):
    """``GET /api/v1/plans/scope-options/`` — selectable calendar scopes."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        scopes = resolve_scopes(request.user)
        return Response(PlanScopeSerializer(scopes, many=True).data)


class TeamPlansView(APIView):
    """``GET /api/v1/plans/team/?scope=&month=YYYY-MM`` — scoped team calendar.

    ``month`` defaults to the current month. ``scope`` defaults to the caller's
    narrowest scope; an unknown or unowned scope token is a 404, never a wider
    view or a silent fallback.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_param = request.query_params.get("month")
        if month_param:
            try:
                year_str, month_str = month_param.split("-")
                year, month = int(year_str), int(month_str)
                month_start = date(year, month, 1)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "month must be in YYYY-MM format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            today = timezone.localdate()
            month_start = date(today.year, today.month, 1)
        if month_start.month == 12:
            month_end = date(month_start.year, 12, 31)
        else:
            month_end = date(
                month_start.year, month_start.month + 1, 1
            ) - timezone.timedelta(days=1)

        scope = find_scope(request.user, request.query_params.get("scope"))
        if scope is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        plans = plans_for_scope(scope, month_start, month_end)
        payload = LeavePlanSerializer(plans, many=True).data
        return Response(
            {
                "scope": {"id": scope.token, "label": scope.label},
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "results": payload,
            }
        )
