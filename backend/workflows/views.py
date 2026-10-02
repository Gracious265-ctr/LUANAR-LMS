from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets

from users.models import Department, EmployeeProfile, User
from users.permissions import IsHRRole

from audit.validation import positive_int, uuid_value
from leave.models import LeaveApplication, LeaveType

from .models import (
    ApproverRole,
    Campus,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
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
    SectionMemberSerializer,
    SectionMemberWriteSerializer,
    TeamReadinessSerializer,
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
    activate_team,
    cancel_delegation,
    deactivate_approver_role,
    deactivate_team,
    is_approver_user,
    reject_delegation,
    remove_role_assignment,
    remove_section_member,
    validate_team,
)


class WorkflowViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Read-only. A chain is written through its team, never on its own.

    Listing and fetching stay, because the team screens and the audit trail
    both need to read a chain — a step's roster and the reason a chain changed
    are things people look up, not just an implementation detail. But
    ``POST``/``PATCH`` are gone: a chain is created with its team and edited
    with it, so the only writer is the one that knows which team's
    applications those steps govern. A write here would change routing for a
    team the person editing never named.
    """

    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return Workflow.objects.prefetch_related(
            "sections__approver_role", "sections__members__user"
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
    :class:`SectionMemberViewSet` rather than as a nested write, so adding or
    removing one person is its own atomic, audited action instead of a
    whole-team overwrite.

    ``status`` is a three-state lifecycle, not a flag, so the list defaults to
    the teams that are actually in force plus the drafts HR is still working on
    (``?status=active``, ``?status=draft``, or ``?include_inactive=1`` for
    everything) rather than hiding the half-built ones HR most needs to see.
    """

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        base = Team.objects.select_related(
            "workflow", "campus", "department"
        ).prefetch_related(
            "workflow__sections__approver_role",
            "workflow__sections__approver",
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
        department = params.get("department")
        if department:
            base = base.filter(
                department_id=positive_int(department, "department")
            )
        return base.order_by("name")

    @action(detail=False, methods=["get"], url_path="eligible-approvers")
    def eligible_approvers(self, request):
        """The employees who may be appointed to a team's approval steps.

        Scoped by the department named on the query, because eligibility *is* the
        department: an approver is one of the team's own employees. Scoping it here
        means the team form's approver picker can only offer people who will pass
        the same rule on write, instead of offering the whole staff and then
        refusing half of them.

        ``?role=<id>`` narrows further to the people already holding that role in
        the department, which is what "one employee holds one role per department"
        makes selectable.
        """
        params = request.query_params
        department_id = params.get("department")
        if not department_id:
            raise drf_serializers.ValidationError(
                {
                    "department": (
                        "Name the department whose employees are eligible. Without "
                        "it there is nothing to scope approvers to."
                    )
                }
            )
        department = Department.objects.filter(
            pk=positive_int(department_id, "department"), is_active=True
        ).first()
        if department is None:
            raise drf_serializers.ValidationError(
                {"department": "That department is missing or is not active."}
            )

        queryset = EmployeeProfile.objects.filter(
            department=department, user__is_active=True
        ).select_related("user", "team")

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
            # One employee, one role per department: offer only the people who
            # already hold this role here, plus whoever holds no role yet. Anyone
            # already appointed in a different role in this department is
            # deliberately absent — the write would refuse them.
            conflicting_ids = set(
                Section.objects.filter(
                    is_active=True,
                    workflow__team__department_id=department.pk,
                )
                .exclude(approver_role_id=role.pk)
                .exclude(approver=None)
                .values_list("approver_id", flat=True)
            )
            holding_ids = set(
                Section.objects.filter(
                    is_active=True,
                    approver_role=role,
                    workflow__team__department_id=department.pk,
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
            # An institution-wide role is held outside any one department, so the
            # holder is absent from the department-scoped queryset above. Offer
            # them anyway: selecting this role *is* how the holder is put on the
            # step, and a picker that could not show them would leave HR with a
            # step no department employee is allowed to fill.
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
                "department": {"id": department.pk, "name": department.name},
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
