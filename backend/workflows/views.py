from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets

from users.models import EmployeeProfile, User
from users.permissions import IsHRRole

from audit.validation import positive_int, uuid_value
from leave.models import LeaveApplication
from leave_config.models import LeaveType

from .models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    TeamRoleAssignment,
    Workflow,
    WorkflowMember,
)
from .permissions import IsApproverRoleOrHR
from .serializers import (
    ApproverRoleSerializer,
    ApproverRoleWriteSerializer,
    CampusRoleAssignmentSerializer,
    CampusSerializer,
    DelegationActionSerializer,
    DelegationSerializer,
    PendingApplicationSerializer,
    ReassignmentSerializer,
    RoleAssignmentSerializer,
    SectionMemberSerializer,
    SectionMemberWriteSerializer,
    TeamMemberAddSerializer,
    TeamMemberSummarySerializer,
    TeamReadinessSerializer,
    TeamRoleAssignmentSerializer,
    TeamSerializer,
    WorkflowMemberPoolSerializer,
    WorkflowMemberSerializer,
    WorkflowMemberWriteSerializer,
    WorkflowSerializer,
    WorkflowWriteSerializer,
)
from .services import (
    DelegationActionError,
    CampusActionError,
    RoleActionError,
    StageSequenceError,
    TeamActionError,
    WorkflowActionError,
    WorkflowMemberError,
    create_campus,
    acting_approver_map,
    approve_delegation,
    activate_team,
    cancel_delegation,
    deactivate_approver_role,
    deactivate_team,
    is_approver_user,
    reject_delegation,
    remove_campus_role_assignment,
    remove_role_assignment,
    remove_section_member,
    remove_team_member,
    remove_team_role_assignment,
    remove_workflow_member,
    team_member_summaries,
    validate_team,
    workflow_member_pool,
)


class WorkflowViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only workflow configuration: read, create, and edit.

    A workflow is written on its own here because a team may own several of
    them and HR configures each separately — create the replacement chain, name
    its stages, and point the team at it when it is ready. Ownership is checked
    by the serializer and the service: a workflow belongs to the team it was
    created for, and a write that would adopt somebody else's chain is refused
    rather than silently re-routing a team.

    ``GET /workflows/?team=<id>`` is the team's workflow listing, which is how
    the team screen finds every chain it owns without reading them all.
    """

    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    # ``delete`` serves the member-removal action only; a workflow itself is
    # removed with its team and is never deleted through this view.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return WorkflowWriteSerializer
        return WorkflowSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, *args, **kwargs):
        """List this workflow's normal members, or add one team member to it.

        Membership is written through the eligibility service, so a person who
        is not on the workflow's team is refused here with the same message the
        pool screen would show — the picker and the write agree because they
        read the same rule.
        """
        workflow = self.get_object()
        if request.method == "POST":
            serializer = WorkflowMemberWriteSerializer(
                data=request.data,
                context={**self.get_serializer_context(), "workflow": workflow},
            )
            serializer.is_valid(raise_exception=True)
            try:
                member = serializer.save()
            except WorkflowMemberError as exc:
                return Response(
                    {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
                )
            except IntegrityError as exc:
                # Concurrent assign of the same person: the unique constraints
                # on (workflow, user) and (team, user) are the backstop behind
                # the service-level eligibility check.
                return Response(
                    {"user": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                WorkflowMemberSerializer(member).data,
                status=status.HTTP_201_CREATED,
            )
        members = workflow.workflow_members.select_related(
            "user", "team", "added_by"
        ).order_by("user__first_name", "user__last_name", "user_id")
        return Response(WorkflowMemberSerializer(members, many=True).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="members/(?P<user_id>[^/.]+)",
    )
    def remove_member(self, request, *args, **kwargs):
        """Remove one normal member from this workflow's pool."""
        workflow = self.get_object()
        user_id = positive_int(kwargs["user_id"], "user_id")
        member = WorkflowMember.objects.filter(
            workflow=workflow, user_id=user_id
        ).first()
        if member is None:
            return Response(
                {"user": ["That person is not a normal member of this workflow."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            remove_workflow_member(member=member, actor=request.user)
        except WorkflowMemberError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_409_CONFLICT
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = Workflow.objects.select_related("team").prefetch_related(
            "sections__approver_role", "sections__members__user"
        )
        if self.action != "list":
            return queryset.order_by("name")
        team = self.request.query_params.get("team")
        if team:
            queryset = queryset.filter(team_id=positive_int(team, "team"))
        routing = self.request.query_params.get("routing")
        if routing == "1":
            queryset = queryset.filter(routed_by__isnull=False)
        elif routing == "0":
            queryset = queryset.filter(routed_by__isnull=True)
        return queryset.order_by("name")

    def _write_response(self, workflow):
        return Response(
            WorkflowSerializer(
                workflow, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            workflow = serializer.save()
        except (WorkflowActionError, StageSequenceError, WorkflowMemberError) as exc:
            field = getattr(exc, "field", "detail")
            message = getattr(exc, "message", str(exc))
            return Response(
                {field: [message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return self._write_response(workflow)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        try:
            workflow = serializer.save()
        except (WorkflowActionError, StageSequenceError, WorkflowMemberError) as exc:
            field = getattr(exc, "field", "detail")
            message = getattr(exc, "message", str(exc))
            return Response(
                {field: [message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            WorkflowSerializer(
                workflow, context=self.get_serializer_context()
            ).data
        )


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
        try:
            role = serializer.save()
        except RoleActionError as exc:
            # A name that cannot form a code is the caller's mistake, not a
            # server fault, so it comes back as a field error rather than a 500.
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
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


class TeamRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Team-wide role holdings (HR only).

    One holder per role per team, and writing a second one replaces the first:
    the screen is a pick-a-role, pick-a-person form, and asking HR to delete
    before they can change their mind is a step that only exists to satisfy the
    database. The service audits both the appointment and the replacement.
    """

    serializer_class = TeamRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = TeamRoleAssignment.objects.select_related(
            "user", "role", "team"
        )
        team = self.request.query_params.get("team")
        if team:
            queryset = queryset.filter(team_id=positive_int(team, "team"))
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=positive_int(user, "user"))
        return queryset.order_by("role__label")

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
            self.get_serializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        remove_team_role_assignment(
            assignment=self.get_object(), actor=request.user
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CampusRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Campus-wide role holdings (HR only).

    Scoped to a campus, so the same holding resolves for every team *at* that
    campus and for no team anywhere else. Same one-holder, replace-on-save
    contract as the team-wide holding.
    """

    serializer_class = CampusRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = CampusRoleAssignment.objects.select_related(
            "user", "role", "campus"
        )
        campus = self.request.query_params.get("campus")
        if campus:
            queryset = queryset.filter(campus_id=positive_int(campus, "campus"))
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=positive_int(user, "user"))
        return queryset.order_by("role__label")

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
            self.get_serializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        remove_campus_role_assignment(
            assignment=self.get_object(), actor=request.user
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    """HR-only CRUD for teams, plus their lifecycle actions (no hard delete).

    A team is created in one pass, optionally with its whole approval chain, and
    put into force by a separate validated action. Members are edited through
    :class:`SectionMemberViewSet` (approver periods), the members actions on
    this viewset (normal team membership), and the workflow member actions —
    each add/remove is its own atomic, audited action instead of a whole-team
    overwrite.

    ``status`` is a three-state lifecycle, not a flag, so the list defaults to
    the teams that are actually in force plus the drafts HR is still working on
    (``?status=active``, ``?status=draft``, or ``?include_inactive=1`` for
    everything) rather than hiding the half-built ones HR most needs to see.
    """

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    # ``delete`` is only routed to the member-removal action; the viewset has
    # no ``destroy`` mixin, so deleting a team itself is still refused. Teams
    # are retired, never deleted, and that stays true.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        base = Team.objects.select_related(
            "workflow", "campus"
        ).prefetch_related(
            "workflow__sections__approver_role",
            "workflow__sections__approver",
            "workflows",
        )
        # Filters are for the *list*. A detail or action route must be able to
        # reach a team whatever its status: a retired team is exactly the one HR
        # needs to read, and refusing to return it would make the 404 the only
        # way to learn a team had been retired.
        if self.action != "list":
            return base.order_by("name")

        params = self.request.query_params
        if params.get("include_inactive") == "1":
            return base.order_by("name")
        requested = params.get("status")
        if requested is not None:
            if requested not in Team.Status.values:
                # A DRF ValidationError, not Django's: only the former is
                # translated into a 400 by the exception handler, and an
                # unhandled one would surface a typo'd filter as a 500.
                raise drf_serializers.ValidationError(
                    {
                        "status": (
                            f"'{requested}' is not a team status. Use "
                            f"{', '.join(Team.Status.values)}."
                        )
                    }
                )
            base = base.filter(status=requested)
        else:
            base = base.exclude(status=Team.Status.INACTIVE)
        campus = params.get("campus")
        if campus:
            base = base.filter(campus_id=positive_int(campus, "campus"))
        category = params.get("category")
        if category:
            if category not in Team.Category.values:
                raise drf_serializers.ValidationError(
                    {
                        "category": (
                            f"'{category}' is not a team category. Use "
                            f"{', '.join(Team.Category.values)}."
                        )
                    }
                )
            base = base.filter(category=category)
        return base.order_by("name")

    @action(detail=False, methods=["get"], url_path="eligible-approvers")
    def eligible_approvers(self, request):
        """The employees who may be appointed to a team's approval steps.

        Scoped by the team named on the query, because eligibility *is* the team:
        an approver is one of the team's own employees. Scoping it here means the
        team form's approver picker can only offer people who will pass the same
        rule on write, instead of offering the whole staff and then refusing half
        of them.

        ``?role=<id>`` narrows further to the people already holding that role in
        the team, which is what "one employee holds one role per team" makes
        selectable.

        ``?workflow=<id>`` shapes the pool for one of the team's chains: people
        already placed on a *different* chain of the team (as a step approver or
        as a normal member) are dropped, because one employee serves one chain of
        a team at a time. ``?workflow=new`` does the same while configuring a
        chain that does not exist yet, so it drops anyone on *any* of the team's
        chains. A wide approver — institution-wide, team-wide on this team, or
        campus-wide at this team's campus — is the exception and stays offered,
        matching the rule the write path enforces.
        """
        params = request.query_params
        team_id = params.get("team")
        if not team_id:
            raise drf_serializers.ValidationError(
                {
                    "team": (
                        "Name the team whose employees are eligible. Without it "
                        "there is nothing to scope approvers to."
                    )
                }
            )
        team = Team.objects.filter(pk=positive_int(team_id, "team")).first()
        if team is None:
            raise drf_serializers.ValidationError(
                {"team": "That team is missing."}
            )

        queryset = EmployeeProfile.objects.filter(
            team=team, user__is_active=True
        ).select_related("user", "team")

        workflow_filter = params.get("workflow")
        if workflow_filter:
            if workflow_filter == "new":
                excluded_workflow_ids: set[int] = set()
            else:
                excluded_workflow_ids = {positive_int(workflow_filter, "workflow")}
            assigned_ids = set(
                WorkflowMember.objects.filter(team=team)
                .exclude(workflow_id__in=excluded_workflow_ids)
                .values_list("user_id", flat=True)
            )
            assigned_ids.update(
                Section.objects.filter(
                    is_active=True,
                    approver__isnull=False,
                    workflow__team=team,
                )
                .exclude(workflow_id__in=excluded_workflow_ids)
                .values_list("approver_id", flat=True)
            )
            wide_ids = set(
                RoleAssignment.objects.filter(
                    role__is_institution_wide=True, user__is_active=True
                ).values_list("user_id", flat=True)
            )
            wide_ids.update(
                TeamRoleAssignment.objects.filter(
                    team=team, user__is_active=True
                ).values_list("user_id", flat=True)
            )
            if team.campus_id is not None:
                wide_ids.update(
                    CampusRoleAssignment.objects.filter(
                        campus_id=team.campus_id, user__is_active=True
                    ).values_list("user_id", flat=True)
                )
            queryset = queryset.exclude(user_id__in=assigned_ids - wide_ids)

        role = None
        role_id = params.get("role")
        if role_id:
            role = ApproverRole.objects.filter(
                pk=positive_int(role_id, "role")
            ).first()
            if role is None:
                raise drf_serializers.ValidationError(
                    {"role": "That approver role is missing."}
                )
            # One employee, one role per team: offer only the people who already
            # hold this role here, plus whoever holds no role yet. Anyone already
            # appointed in a different role on this team is deliberately absent —
            # the write would refuse them.
            conflicting_ids = set(
                Section.objects.filter(
                    is_active=True,
                    workflow__team__pk=team.pk,
                )
                .exclude(approver_role_id=role.pk)
                .exclude(approver=None)
                .values_list("approver_id", flat=True)
            )
            holding_ids = set(
                Section.objects.filter(
                    is_active=True,
                    approver_role=role,
                    workflow__team__pk=team.pk,
                )
                .exclude(approver=None)
                .values_list("approver_id", flat=True)
            )
            queryset = queryset.exclude(
                user_id__in=conflicting_ids - holding_ids
            )

        candidates = list(
            queryset.order_by("user__first_name", "user__last_name")
        )
        if role is not None and role.is_institution_wide:
            # An institution-wide role is held outside any one team, so the holder
            # is absent from the team-scoped queryset above. Offer them anyway:
            # selecting this role *is* how the holder is put on the step, and a
            # picker that could not show them would leave HR with a step no team
            # member is allowed to fill.
            already_offered = {profile.user_id for profile in candidates}
            holder_ids = RoleAssignment.objects.filter(
                role=role, user__is_active=True
            ).values_list("user_id", flat=True)
            candidates.extend(
                EmployeeProfile.objects.filter(
                    user_id__in=holder_ids, user__is_active=True
                )
                .exclude(user_id__in=already_offered)
                .select_related("user", "team")
            )

        return response.Response(
            {
                "team": {"id": team.pk, "name": team.name},
                "candidates": [
                    {
                        "id": profile.user_id,
                        "full_name": profile.user.get_full_name()
                        or profile.user.username,
                        "email": profile.user.email,
                        "designation": profile.designation,
                    }
                    for profile in candidates
                ],
            }
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, *args, **kwargs):
        """List this team's normal members, or place one employee on it.

        GET is the team members screen's roster: every employee whose
        :attr:`EmployeeProfile.team` is this team, with the workflow they are a
        normal member of and whether they also staff a step or hold a team-wide
        role. POST places one employee through the same guards the service
        applies, so a picker that offers a candidate from another team gets a
        refusal naming that team rather than a silent move.
        """
        team = self.get_object()
        if request.method == "POST":
            serializer = TeamMemberAddSerializer(
                data=request.data, context={**self.get_serializer_context(), "team": team}
            )
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save()
            except WorkflowMemberError as exc:
                return Response(
                    {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
                )
            except IntegrityError as exc:
                return Response(
                    {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                TeamMemberSummarySerializer(team_member_summaries(team), many=True).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            TeamMemberSummarySerializer(team_member_summaries(team), many=True).data
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path="members/(?P<user_id>[^/.]+)",
    )
    def remove_member(self, request, *args, **kwargs):
        """Take one employee off this team, refusing while they hold a role.

        A refusal names every responsibility that still ties them to the team
        (step appointment, open approver period, normal workflow membership,
        team-wide holding) so HR can release them one by one rather than being
        sent back with a single "cannot remove".
        """
        team = self.get_object()
        user_id = positive_int(kwargs["user_id"], "user_id")
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response(
                {"user": ["That employee account is missing."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            remove_team_member(team=team, user=user, actor=request.user)
        except WorkflowMemberError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_409_CONFLICT
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="workflow-member-pool")
    def workflow_members_pool(self, request, *args, **kwargs):
        """Who may be assigned to a workflow as a normal member of this team.

        ``?workflow=<id>`` scopes the answer to one of the team's own chains so
        its current members are listed as already-selected and people on other
        chains are listed as assigned elsewhere. Without it the pool is
        "everybody on the team who is not already on one of our chains", which
        is what the create-workflow screen needs.
        """
        team = self.get_object()
        workflow = None
        workflow_id = request.query_params.get("workflow")
        if workflow_id:
            workflow = Workflow.objects.filter(
                pk=positive_int(workflow_id, "workflow"), team=team
            ).first()
            if workflow is None:
                return Response(
                    {"workflow": ["That workflow is missing or is not this team's."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(
            WorkflowMemberPoolSerializer(
                workflow_member_pool(team=team, workflow=workflow)
            ).data
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            team = serializer.save()
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
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
        try:
            team = serializer.save()
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            TeamSerializer(team, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_configuration(self, request, *args, **kwargs):
        """Report whether this team could be activated, without changing it.

        Side-effect free and available at any status, so HR can check a team that
        is already in force and find out which step has lost its approver — the
        question that otherwise only surfaces as a refused submission from the
        employee. The same function gates the activate action, so the answer here
        is exactly the answer activation would give.
        """
        team = self.get_object()
        readiness = validate_team(team)
        return Response(TeamReadinessSerializer(readiness).data)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, *args, **kwargs):
        """Put a draft team into force, refusing a team that cannot route.

        A refusal is a 400 carrying the full list of issues rather than the first
        one, and the team stays a draft: the configuration HR wrote is intact and
        every problem is named, so this is a to-do list and not a dead end.
        """
        team = self.get_object()
        try:
            activated = activate_team(team=team, actor=request.user)
        except TeamActionError as exc:
            payload: dict = {exc.field: [exc.message]}
            if exc.issues:
                payload["issues"] = [
                    {
                        "code": issue.code,
                        "field": issue.field,
                        "message": issue.message,
                        "section": issue.section,
                        "approver_role": issue.approver_role,
                    }
                    for issue in exc.issues
                ]
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TeamSerializer(activated, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, *args, **kwargs):
        """Retire a team from routing, keeping its configuration and history.

        Applications already inside the team's chain keep the stages they were
        submitted with, so they can still be decided; only new submissions stop
        following the team. There is no hard delete for that reason.
        """
        team = self.get_object()
        try:
            retired = deactivate_team(team=team, actor=request.user)
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            TeamSerializer(retired, context=self.get_serializer_context()).data
        )


class SectionMemberViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Who has acted for a section, and the appointment of its approver.

    Appointing somebody is its own atomic, audited action rather than part of a
    whole-workflow write, so changing one step's approver cannot silently rewrite
    the rest of the chain. ``POST`` appoints the one person a step routes to —
    setting :attr:`Section.approver` and opening the effective-dated period that
    records it — and ``DELETE`` closes that period and leaves the step
    unstaffed.

    A step has exactly one approver, so appointing somebody new closes the
    outgoing person's period in the same transaction. Two open periods on one
    step would make "who holds this step" answerable two ways.

    The default view is the people who can act *now*. ``?history=1`` widens it to
    every period, closed ones included, because a membership row is a record of
    who was entitled to act and when — and a chain that once had an approver must
    still be explainable after they have gone.
    """

    serializer_class = SectionMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        # Reads want the dates and the "is this in force right now" flag; writes
        # are the smaller payload the service actually takes.
        if self.action == "create":
            return SectionMemberWriteSerializer
        return SectionMemberSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = (
            SectionMember.all_objects
            if params.get("history") == "1"
            else SectionMember.objects
        ).select_related("section", "section__workflow", "user")
        section = params.get("section")
        if section:
            queryset = queryset.filter(section_id=positive_int(section, "section"))
        workflow = params.get("workflow")
        if workflow:
            queryset = queryset.filter(
                section__workflow_id=positive_int(workflow, "workflow")
            )
        user = params.get("user")
        if user:
            queryset = queryset.filter(user_id=positive_int(user, "user"))
        return queryset.order_by("section__order", "user__last_name")

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
            SectionMemberSerializer(
                membership, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        # Closing a membership can legitimately be refused — a period that has
        # not started yet has to be removed outright instead of "ended", and a
        # caller may pass an end date before the start.
        try:
            remove_section_member(membership=self.get_object(), actor=request.user)
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
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
