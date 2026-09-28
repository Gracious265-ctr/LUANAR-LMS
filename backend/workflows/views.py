from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, status
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets

from users.models import User
from users.permissions import IsHRRole

from audit.validation import positive_int, uuid_value
from leave.models import LeaveApplication, LeaveType

from .models import (
    ApproverRole,
    Campus,
    Delegation,
    Reassignment,
    RoleAssignment,
    Team,
    TeamMember,
    Workflow,
)
from .permissions import IsApproverRoleOrHR
from .serializers import (
    ApproverRoleSerializer,
    ApproverRoleWriteSerializer,
    CampusSerializer,
    DelegationActionSerializer,
    DelegationSerializer,
    PendingApplicationSerializer,
    ReassignmentSerializer,
    RoleAssignmentSerializer,
    TeamMemberSerializer,
    TeamSerializer,
    WorkflowSerializer,
)
from .services import (
    DelegationActionError,
    CampusActionError,
    RoleActionError,
    TeamActionError,
    create_campus,
    acting_approver_map,
    approve_delegation,
    cancel_delegation,
    deactivate_approver_role,
    is_approver_user,
    reject_delegation,
    remove_role_assignment,
    remove_team_member,
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


class ApproverRoleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for approver roles (no hard delete).

    ``DELETE`` maps to :func:`deactivate_approver_role`, which refuses while the
    role is still referenced by an active workflow, a team, or a holder. That is
    why this viewset — unlike the other configuration endpoints — allows DELETE:
    the client sees a 204 for a retired role and a 409 for one still in use.
    """

    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return ApproverRoleWriteSerializer
        return ApproverRoleSerializer

    def get_queryset(self):
        queryset = ApproverRole.objects.all()
        if self.request.query_params.get("include_inactive") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("label")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        return Response(
            ApproverRoleSerializer(role, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", True)
        )
        serializer.is_valid(raise_exception=True)
        try:
            role = serializer.save()
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(ApproverRoleSerializer(role, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        try:
            role = deactivate_approver_role(
                role=self.get_object(), actor=request.user
            )
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_409_CONFLICT
            )
        return Response(
            ApproverRoleSerializer(role, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class RoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Institution-wide role holdings (HR only).

    Institution-wide roles need no per-application row: the provider checks
    holders of an active institution-wide role whenever a stage's role has no
    team member. Registrars are the canonical case — a single institution-wide
    registrar handles every leave application.
    """

    serializer_class = RoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = RoleAssignment.objects.select_related("user", "role")
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=positive_int(user, "user"))
        return queryset.order_by("role__label", "user_id")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = serializer.save()
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            RoleAssignmentSerializer(
                assignment, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        remove_role_assignment(assignment=self.get_object(), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for teams (no hard delete).

    Members are edited through :class:`TeamMemberViewSet` rather than as a nested
    write, so adding or removing one person is its own atomic, audited action
    instead of a whole-team overwrite.
    """

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Team.objects.select_related("workflow", "campus").prefetch_related(
            "memberships__user", "memberships__role"
        )
        if self.request.query_params.get("include_inactive") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = serializer.save()
        return Response(
            TeamSerializer(team, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", True)
        )
        serializer.is_valid(raise_exception=True)
        team = serializer.save()
        return Response(
            TeamSerializer(team, context=self.get_serializer_context()).data
        )


class TeamMemberViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Membership of a team, in one role each."""

    serializer_class = TeamMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = TeamMember.objects.select_related("team", "user", "role")
        team = self.request.query_params.get("team")
        if team:
            queryset = queryset.filter(team_id=positive_int(team, "team"))
        return queryset.order_by("team__name", "role__label")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = serializer.save()
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TeamMemberSerializer(
                membership, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        remove_team_member(membership=self.get_object(), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CampusViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-managed campus reference data (no hard delete).

    ``PROTECT`` on Team.campus is deliberate: deleting a campus that a team
    points at would silently change what "this team's campus" means, so a
    campus is only ever deactivated.
    """

    serializer_class = CampusSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Campus.objects.all()
        if self.request.query_params.get("include_inactive") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campus = serializer.save()
        except CampusActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            CampusSerializer(campus, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", True)
        )
        serializer.is_valid(raise_exception=True)
        try:
            campus = serializer.save()
        except CampusActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            CampusSerializer(campus, context=self.get_serializer_context()).data
        )
