from django.db.models import Q
from django.http import Http404
from rest_framework import mixins, permissions, viewsets

from leave.models import LeaveApplication
from leave_config.models import LeaveType
from users.permissions import IsHRRole

from .models import AuditEntry
from .serializers import (
    AuditEntrySerializer,
    FinalizedApplicationListSerializer,
    HRLeaveApplicationSerializer,
)
from .validation import positive_int


class AuditEntryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only read access to the append-only audit log."""

    serializer_class = AuditEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        queryset = AuditEntry.objects.select_related("actor")
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        target_id = self.request.query_params.get("target_id")
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        actor = self.request.query_params.get("actor")
        if actor:
            queryset = queryset.filter(actor_id=positive_int(actor, "actor"))
        return queryset


class FinalizedLeaveViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only organization-wide read of in-flight and approved applications.

    Unit 25 (D6): the view previously filtered ``SUBMITTED`` only, so an
    approved — i.e. actually finalized — application was invisible to HR and
    ``get_object`` 404'd it. Rejected and cancelled applications stay out; the
    audit log is the record of those (Unit 24 D1).
    """

    serializer_class = HRLeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "head", "options"]

    #: The statuses HR treats as "in flight or finalized" (Unit 25 D6).
    VISIBLE_STATUSES = (
        LeaveApplication.Status.SUBMITTED,
        LeaveApplication.Status.APPROVED,
    )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HRLeaveApplicationSerializer
        return FinalizedApplicationListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "list":
            context["leave_type_names"] = dict(
                LeaveType.objects.values_list("id", "name")
            )
        return context

    def get_queryset(self):
        queryset = LeaveApplication.objects.filter(
            status__in=self.VISIBLE_STATUSES
        ).select_related("employee", "current_approver")
        search = self.request.query_params.get("employee")
        if search:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=search)
                | Q(employee__last_name__icontains=search)
                | Q(employee__email__icontains=search)
            )
        return queryset.order_by("-submitted_at")

    def get_object(self):
        obj = super().get_object()
        if obj.status not in self.VISIBLE_STATUSES:
            raise Http404("Not found.")
        return obj