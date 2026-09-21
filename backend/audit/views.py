from django.db.models import Q
from django.http import Http404
from rest_framework import mixins, permissions, viewsets

from leave.models import LeaveApplication
from users.permissions import IsHRRole

from .models import AuditEntry
from .serializers import AuditEntrySerializer, HRLeaveApplicationSerializer
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
    """HR-only organization-wide read of submitted (finalized) applications."""

    serializer_class = HRLeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        queryset = LeaveApplication.objects.filter(
            status=LeaveApplication.Status.SUBMITTED
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
        if obj.status != LeaveApplication.Status.SUBMITTED:
            raise Http404("Not found.")
        return obj