"""HTTP API for teams: CRUD/lifecycle, membership, and holdings.

``TeamViewSet`` was split out of ``workflows.views`` and
``TeamRoleAssignmentViewSet`` out of ``organisation.views`` so the ``teams`` app
owns the team surface end to end. The workflow- and section-membership viewsets
they used to sit beside stay in ``workflows``; the service functions they call
still live in ``workflows.services`` and ``organisation.services``.
"""

from django.db import IntegrityError
from rest_framework import mixins, permissions, response, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers

from audit.validation import positive_int
from users.models import EmployeeProfile, User

from organisation.models import (
    ApproverRole,
    CampusRoleAssignment,
    RoleAssignment,
)
from organisation.permissions import IsHROnly, IsHROrTeamManager
from organisation.services import (
    RoleActionError,
    WorkflowMemberError,
    clear_team_manager,
    managed_team_ids,
    remove_team_role_assignment,
    set_team_manager,
    team_manager_profile,
    wide_approver_ids_for_team,
)
from teams.models import Team, TeamRoleAssignment
from teams.serializers import (
    TeamMemberAddSerializer,
    TeamMemberSummarySerializer,
    TeamReadinessSerializer,
    TeamRoleAssignmentSerializer,
    TeamSerializer,
    WorkflowMemberPoolSerializer,
)
from workflows.models import Section, Workflow, WorkflowMember
from workflows.permissions import IsTeamManagerOnly
from workflows.policies import can_manage_team
from workflows.services import (
    TeamActionError,
    deactivate_team,
    remove_team_member,
    team_member_summaries,
    validate_team,
    workflow_member_pool,
)


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    """HR-only CRUD for teams, plus their lifecycle actions (no hard delete).

    A team is created in force in one pass and retired by a separate validated
    action. Members are edited through :class:`SectionMemberViewSet` (approver
    periods), the members actions on this viewset (normal team membership), and
    the workflow member actions — each add/remove is its own atomic, audited
    action instead of a whole-team overwrite.

    ``status`` is a two-state lifecycle, not a flag, so the list defaults to the
    teams that are actually in force (``?status=active``, or ``?include_inactive=1``
    for everything, retired teams included) rather than hiding the retired ones
    HR may still need to see.
    """

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    # ``delete`` is only routed to the member-removal action; the viewset has
    # no ``destroy`` mixin, so deleting a team itself is still refused. Teams
    # are retired, never deleted, and that stays true.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        """HR keeps the team's identity and lifecycle; a manager keeps its people.

        Creating a team, editing its category/campus/details, assigning its
        manager, and moving it in or out of force are HR decisions. Everything
        else on this viewset — reading, listing members, adding/removing members,
        and shaping the workflow pool — is the team's manager's, filtered to
        their own team by :meth:`get_queryset`.
        """
        if self.action in (
            "create",
            "update",
            "partial_update",
            "deactivate",
        ):
            return [permissions.IsAuthenticated(), IsHROnly()]
        if self.action in (
            "members",
            "member_candidates",
            "workflow_members_pool",
        ):
            # Adding and removing the roster — and reading who may be added to a
            # chain — are the manager's calls once HR has created the team and
            # designated them. HR stays out of it rather than merely scoping the
            # manager to their own team, so the handover is the whole boundary.
            return [permissions.IsAuthenticated(), IsTeamManagerOnly()]
        # Remove-member is a detail action on members (DELETE)
        if self.action == "remove_member":
            return [permissions.IsAuthenticated(), IsTeamManagerOnly()]
        return super().get_permissions()

    def get_queryset(self):
        base = Team.objects.select_related(
            "campus"
        ).prefetch_related(
            "workflows__sections__approver_role",
            "workflows__sections__approver",
            "workflows",
        )
        managed = managed_team_ids(self.request.user)
        if managed is not None:
            base = base.filter(pk__in=managed)
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
        if not can_manage_team(request.user, team):
            # A manager may only shape the pool of their own team; naming another
            # team's id must not leak its roster.
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

    @action(detail=True, methods=["get"], url_path="member-candidates")
    def member_candidates(self, request, *args, **kwargs):
        """Employees who may be added to this team's roster.

        The team members picker reads this. It lists exactly who the
        ``members`` write would accept, so nothing is offered only to be
        refused there: active employees who hold no team yet, who share the
        category of this team's **manager**, and who are not wide approvers for
        it. Measuring against the manager rather than the team record is the
        rule the roster is built around; a team not yet handed to a manager has
        none, so its own category stands in there. Both sides of the picker are
        team-scoped through ``get_object``, so a team's manager reads their own
        roster's candidates and no other team's.
        """
        team = self.get_object()
        manager_profile = team_manager_profile(team)
        governing = manager_profile if manager_profile is not None else team
        queryset = (
            EmployeeProfile.objects.filter(
                user__is_active=True,
                team__isnull=True,
                category=governing.category,
            )
            .exclude(user_id__in=wide_approver_ids_for_team(team))
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "user_id")
        )
        return Response(
            [
                {
                    "id": profile.user_id,
                    "full_name": profile.user.get_full_name()
                    or profile.user.username,
                    "email": profile.user.email,
                    "designation": profile.designation,
                }
                for profile in queryset
            ]
        )

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
        except (TeamActionError, RoleActionError) as exc:
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
        except (TeamActionError, RoleActionError) as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            TeamSerializer(team, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_configuration(self, request, *args, **kwargs):
        """Report whether this team's configuration can route, without changing it.

        Side-effect free and available at any status, so HR can check a team that
        is already in force and find out which step has lost its approver — the
        question that otherwise only surfaces as a refused submission from the
        employee. Teams are in force from creation now, so this is not a gate
        before activation; it is the standing answer to "can this chain carry an
        application", naming every problem rather than only the first.
        """
        team = self.get_object()
        readiness = validate_team(team)
        return Response(TeamReadinessSerializer(readiness).data)

    # There is deliberately no ``activate``: creating a team puts it in force,
    # so a "put into force now" button would be a second confirmation of
    # something that already happened. Only the way back out — deactivation —
    # remains an action, because retiring a team is a decision that still has to
    # be taken.

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


class TeamRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Team-wide role holdings.

    One holder per role per team, and writing a second one replaces the first:
    the screen is a pick-a-role, pick-a-person form, and asking HR to delete
    before they can change their mind is a step that only exists to satisfy the
    database. The service audits both the appointment and the replacement.

    A team manager may **read** the holdings — their team's chain builder scopes
    which roles it offers from which teams hold one, and shows the holder on a
    team-wide step. Only HR may change a holding.
    """

    serializer_class = TeamRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [permissions.IsAuthenticated(), IsHROnly()]
        return super().get_permissions()

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

    @action(detail=True, methods=["post"], url_path="set-manager")
    def set_manager(self, request, *args, **kwargs):
        """Designate this team-wide holding as its team's manager (HR only)."""
        try:
            assignment = set_team_manager(
                assignment=self.get_object(), actor=request.user
            )
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(self.get_serializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="clear-manager")
    def clear_manager(self, request, *args, **kwargs):
        """Remove the manager designation from this holding (HR only)."""
        try:
            assignment = clear_team_manager(
                assignment=self.get_object(), actor=request.user
            )
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(self.get_serializer(assignment).data)
