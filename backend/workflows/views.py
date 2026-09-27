from django.db.models import Q
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, status
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets

from users.models import User
from users.permissions import IsHRRole

from audit.validation import uuid_value
from leave.models import LeaveApplication, LeaveType

from .models import Delegation, Reassignment, Workflow
from .permissions import IsApproverRoleOrHR
from .serializers import (
    DelegationActionSerializer,
    DelegationSerializer,
    PendingApplicationSerializer,
    ReassignmentSerializer,
    WorkflowSerializer,
)
from .services import (
    DelegationActionError,
    acting_approver_map,
    approve_delegation,
    cancel_delegation,
    is_approver_user,
    reject_delegation,
)


class WorkflowViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for approval workflows (no hard delete)."""

    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Workflow.objects.prefetch_related("stages")


class DelegateCandidateSerializer(drf_serializers.ModelSerializer):
    """Minimal approver shape for the delegate picker.

    Deliberately narrower than the HR ``EmployeeSerializer``: an approver needs
    a name and a role to pick a delegate, not the whole employee record.
    """

    full_name = drf_serializers.CharField(
        source="get_full_name", read_only=True
    )

    class Meta:
        model = User
        fields = ["id", "full_name", "role"]


class DelegationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Delegation requests, HR decisions, and active management.

    ``create`` is open to active approvers (self-service) and HR (on behalf).
    ``list``/``retrieve`` are open to HR (everything) and to approvers, who see
    only the delegations they are a party to. The approve/reject/cancel actions
    stay HR-only.
    """

    serializer_class = DelegationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "candidates"):
            return [permissions.IsAuthenticated(), IsApproverRoleOrHR()]
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated(), IsApproverRoleOrHR()]
        return [permissions.IsAuthenticated(), IsHRRole()]

    def get_queryset(self):
        queryset = Delegation.objects.select_related(
            "approver", "delegate", "requested_by", "decided_by"
        )
        user = self.request.user
        if getattr(user, "role", None) != User.Role.HR:
            # An approver only ever sees their own side of the story. Scoping the
            # queryset (rather than checking per object) also makes ``retrieve``
            # 404 on someone else's delegation instead of leaking its existence.
            queryset = queryset.filter(Q(approver=user) | Q(delegate=user))
        state = self.request.query_params.get("state")
        today = timezone.localdate()
        if state == "requested":
            queryset = queryset.filter(status=Delegation.Status.REQUESTED)
        elif state == "rejected":
            queryset = queryset.filter(status=Delegation.Status.REJECTED)
        elif state == "cancelled":
            queryset = queryset.filter(status=Delegation.Status.CANCELLED)
        elif state == "scheduled":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, starts_on__gt=today
            )
        elif state == "active":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, starts_on__lte=today
            ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        elif state == "ended":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, ends_on__lt=today
            )

        search = self.request.query_params.get("approver")
        if search:
            queryset = queryset.filter(
                Q(approver__first_name__icontains=search)
                | Q(approver__last_name__icontains=search)
                | Q(approver__email__icontains=search)
            )
        return queryset

    @decorators.action(detail=False, methods=["get"])
    def candidates(self, request):
        """Active approver-role users the caller may nominate as delegate.

        A self-service requester needs this to name a delegate without being
        handed the HR-only employee list. The caller is excluded, because a
        delegation to oneself is rejected on write anyway.
        """
        candidates = [
            user
            for user in User.objects.filter(is_active=True).order_by(
                "first_name", "last_name"
            )
            if is_approver_user(user) and user.pk != request.user.pk
        ]
        return response.Response(
            {
                "candidates": DelegateCandidateSerializer(
                    candidates, many=True
                ).data
            }
        )

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._run_action(request, pk, approve_delegation)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._run_action(request, pk, reject_delegation)

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._run_action(request, pk, cancel_delegation)

    def _run_action(self, request, pk, service):
        delegation = self.get_object()
        payload = DelegationActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            delegation = service(delegation, request.user, payload.validated_data)
        except DelegationActionError as exc:
            raise drf_serializers.ValidationError(
                {exc.field: [exc.message]}
            )
        return response.Response(
            DelegationSerializer(
                delegation, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )


class ReassignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only emergency reassignment of pending applications (no delete)."""

    serializer_class = ReassignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = Reassignment.objects.select_related(
            "application__employee", "from_approver", "to_approver", "decided_by"
        )
        application = self.request.query_params.get("application")
        if application:
            queryset = queryset.filter(
                application_id=uuid_value(application, "application")
            )
        return queryset

    @decorators.action(detail=False, methods=["get"])
    def pending(self, request):
        """The intervention queue: submitted applications awaiting approval.

        Resolved in bulk so the queue stays a fixed number of queries: the
        acting approver (Unit 21 routing) is reported alongside the responsible
        one, which is what tells HR whether a reassignment would actually change
        who holds the application.
        """
        queryset = (
            LeaveApplication.objects.filter(status=LeaveApplication.Status.SUBMITTED)
            .select_related("employee", "current_approver", "current_stage")
            .order_by("-submitted_at")
        )
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        serializer = PendingApplicationSerializer(
            rows,
            many=True,
            context={
                "leave_type_names": dict(
                    LeaveType.objects.values_list("id", "name")
                ),
                "acting_approver_map": acting_approver_map(rows),
            },
        )
        return self.get_paginated_response(serializer.data)
