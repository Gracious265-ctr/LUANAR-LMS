from __future__ import annotations

from django.db import transaction
from rest_framework import mixins, permissions, response, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes

from leave_config.models import LeaveType
from leave_config.serializers import LeaveTypeSerializer
from leave_config.services import (
    AnnualLeaveLifecycleError,
    can_access_leave_config,
    deactivate_leave_type,
    reactivate_leave_type,
)

__all__ = ["LeaveTypeViewSet"]


class IsLeaveConfigAccess(permissions.BasePermission):
    """Read for every authenticated user, writes for HR only (§4.4).

    Every module's dropdowns need the list, but only HR/superuser may create,
    edit, deactivate or reactivate.
    """

    message = "Only HR may change leave types."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return can_access_leave_config(user)


class LeaveTypeViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD for leave types — never a hard delete (§1.5).

    ``DELETE`` is excluded from ``http_method_names`` so it answers 405 rather
    than reaching a viewset; retired types are deactivated instead, leaving
    every application and plan that references them untouched.
    """

    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsLeaveConfigAccess]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = LeaveType.objects.all()
        if self.action != "list":
            return queryset
        # Default (and ?active_only=true) hides retired types; HR's list
        # passes ?include_inactive=true to see them greyed out in place.
        if self.request.query_params.get("include_inactive") == "true":
            return queryset
        return queryset.filter(is_active=True)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def deactivate(self, request, pk=None):
        leave_type = self.get_object()
        try:
            deactivate_leave_type(leave_type, request.user)
        except AnnualLeaveLifecycleError as error:
            # The service is the authority, so its refusal becomes a 400 here
            # rather than a 500 — the annual type is the one row this endpoint
            # exists to protect.
            return response.Response(
                {"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST
            )
        return response.Response(self.get_serializer(leave_type).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reactivate(self, request, pk=None):
        leave_type = self.get_object()
        reactivate_leave_type(leave_type, request.user)
        return response.Response(self.get_serializer(leave_type).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def grade_options(request):
    """The grade ids the eligibility multi-select offers (§1.4).

    Grades are directory data, not leave-configuration data — this endpoint
    only mirrors them so the form can label the ids stored on the type.
    """
    from directory.factory import get_organization_provider

    grades = [
        {"id": record.id, "name": record.name}
        for record in get_organization_provider().get_grades()
    ]
    return response.Response(grades)
