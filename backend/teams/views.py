"""Team management endpoints (moved from chains)."""

from django.db import IntegrityError
from rest_framework import mixins, permissions, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from audit.models import AuditEntry
from audit.services import record_audit
from campuses.models import Campus, CampusRoleAssignment
from chains.models import Section, SectionMember, Workflow, WorkflowMember
from chains.services import (
    StageSequenceError,
    assign_workflow_member,
    remove_team_member,
    create_team,
    deactivate_team,
    normalize_section_sequence,
    remove_workflow_member,
    team_member_summaries,
    update_team,
    validate_team,
    wide_approver_ids_for_team,
    workflow_member_pool,
)
from chains.services.lifecycle import route_team
from chains.serializers import TeamReadinessSerializer, WorkflowMemberPoolSerializer
from chains.services._shared import TeamActionError, _require_can_manage_team
from roles.models import ApproverRole, RoleAssignment
from roles.permissions import IsHROnly, IsHROrTeamManager, is_hr
from roles.services import RoleActionError, WorkflowMemberError, is_team_manager
from chains.views import _managed_team_ids


can_manage_team = _require_can_manage_team

from teams.models import Team, TeamRoleAssignment
from teams.serializers import (
    TeamMemberAddSerializer,
    TeamMemberBulkAddSerializer,
    TeamMemberSummarySerializer,
    TeamSerializer,
)
from roles.serializers import ApproverRoleSerializer, TeamRoleAssignmentSerializer
from users.models import EmployeeProfile, User
from users.serializers import EmployeeSerializer

from .permissions import IsHROrTeamManager as TeamsIsHROrTeamManager


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Must be an integer."}) from exc
    if parsed < 1:
        raise ValidationError({field_name: "Must be a positive integer."})
    return parsed


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    """HR-only CRUD for teams, plus their routing and retirement actions.

    A team is created in one pass, optionally with its whole approval chain, and
    is in force the moment it is created — there is no separate activation step.
    Members are edited through :class:`SectionMemberViewSet` (approver periods),
    the members actions on this viewset (normal team membership), and the
    workflow member actions — each add/remove is its own atomic, audited action
    instead of a whole-team overwrite.

    ``status`` is a three-state lifecycle, not a flag, so the list defaults to
    the teams that are actually in force (``?status=active``, ``?status=draft``,
    or ``?include_inactive=1`` for everything) rather than hiding the retired
    ones.
    """

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    # ``delete`` is only routed to the member-removal action; the viewset has
    # no ``destroy`` mixin, so deleting a team itself is still refused. Teams
    # are retired, never deleted, and that stays true.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        """HR keeps a team's identity and lifecycle; a manager keeps its people.

        Creating a team, and editing its category, campus, or details, are HR
        decisions: a manager inherits a team, they do not decide what it is.
        Everything else — reading, listing members, adding and removing members,
        shaping the workflow pool, and choosing which chain the team routes
        through — is shared, and the scoped queryset keeps a manager on their own
        team.
        """
        if self.action in ("create", "update", "partial_update", "deactivate"):
            return [permissions.IsAuthenticated(), IsHROnly()]
        return super().get_permissions()

    @action(detail=True, methods=["get"], url_path="member-candidates")
    def member_candidates(self, request, *args, **kwargs):
        """The people a manager may place on this team's roster.

        The roster's candidate list is "unassigned employees of the team's own
        half of the institution, who are not already wide approvers for it", and
        the HR employee directory answers it with ``?team=none&category=…``. That
        directory is HR-only, so a team manager building their roster had no way
        to read who was available and could only remove people, never add them.

        The team's own designated manager is offered even though they are a wide
        approver: joining the roster is how their own leave routes through the
        team they run. Once they join, "unassigned employees" excludes them from
        every other team's list.

        This proposes the same list through a route a manager may reach — the
        team is ``self.get_object()``, so the scoped queryset has already
        refused a team that is not theirs — and returns the employee shape the
        picker already renders. It is the read half of ``members`` and nothing
        more: placing somebody still goes through the write path's own guards.
        """
        team = self.get_object()
        queryset = (
            EmployeeProfile.objects.filter(
                team__isnull=True,
                category=team.category,
                user__is_active=True,
            )
            .exclude(user_id__in=wide_approver_ids_for_team(team))
            .select_related("user", "team")
            .order_by("user__first_name", "user__last_name")
        )
        return Response(
            [EmployeeSerializer(profile).data for profile in queryset]
        )

    @action(detail=False, methods=["get"], url_path="eligible-approver-roles")
    def eligible_approver_roles(self, request):
        """The approver roles a manager may pick from when describing a chain.

        The workflow form's role list is the same one HR reads, but that route is
        HR-only, so a manager opening "New workflow" saw no roles and the Add-step
        and Create-workflow buttons were disabled — a form they could not operate.
        A role is not secret configuration (a manager names steps with it), so the
        list is exposed read-only here: active roles only, and only to a caller
        who manages at least one team, which ``IsHROrTeamManager`` already gates.
        A manager may also *create* a role by name on the role endpoint, deduped
        by name; editing and retiring one stay HR's.
        """
        roles = ApproverRole.objects.filter(is_active=True).order_by("label")
        return Response(ApproverRoleSerializer(roles, many=True).data)

    def get_queryset(self):
        base = Team.objects.select_related(
            "workflow", "campus"
        ).prefetch_related(
            "workflow__sections__approver_role",
            "workflow__sections__approver",
            "workflows",
        )
        managed = _managed_team_ids(self.request.user)
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
            base = base.filter(campus_id=_positive_int(campus, "campus"))
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
        team = Team.objects.filter(pk=_positive_int(team_id, "team")).first()
        if team is None:
            raise drf_serializers.ValidationError(
                {"team": "That team is missing."}
            )
        # A detail=False action answers for the team named on the query rather
        # than through ``get_object``, so the manager scoping the rest of the
        # viewset gets from ``get_queryset`` has to be applied by hand here.
        managed = _managed_team_ids(request.user)
        if managed is not None and team.pk not in managed:
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
                excluded_workflow_ids = {_positive_int(workflow_filter, "workflow")}
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
            # A team-wide holder staffs the steps of every chain — including the
            # team's designated manager, whose holding is a post rather than an
            # enrolment — so they stay offered even after staffing another
            # chain, exactly as the write path now accepts them.
            wide_ids = wide_approver_ids_for_team(team) | set(
                TeamRoleAssignment.objects.filter(
                    team=team, user__is_active=True
                ).values_list("user_id", flat=True)
            )
            queryset = queryset.exclude(user_id__in=assigned_ids - wide_ids)

        role = None
        role_id = params.get("role")
        if role_id:
            role = ApproverRole.objects.filter(
                pk=_positive_int(role_id, "role")
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
        if role is not None:
            # A wide holding staffs this role's steps from outside the team
            # roster, so its holder is absent from the team-scoped queryset
            # above. Offer them anyway: selecting the role is how the holder is
            # put on a step, and a picker that could not show them would leave
            # the step unfillable.
            #
            # The scope is the same one routing applies: the team's own holder,
            # the holder at the campus of an *academic* team, and — for an
            # *administration* team only — the institution-wide holder. A
            # campus-wide approver never reaches a team at another campus, and
            # an institution-wide approver never reaches an academic team.
            wide_holder_ids = set(
                TeamRoleAssignment.objects.filter(
                    team=team, role=role, user__is_active=True
                ).values_list("user_id", flat=True)
            )
            if team.category == Team.Category.ACADEMIC and team.campus_id is not None:
                wide_holder_ids.update(
                    CampusRoleAssignment.objects.filter(
                        campus_id=team.campus_id, role=role, user__is_active=True
                    ).values_list("user_id", flat=True)
                )
            if (
                role.is_institution_wide
                and team.category == Team.Category.ADMINISTRATION
            ):
                wide_holder_ids.update(
                    RoleAssignment.objects.filter(
                        role=role, user__is_active=True
                    ).values_list("user_id", flat=True)
                )
            already_offered = {profile.user_id for profile in candidates}
            holder_ids = wide_holder_ids - conflicting_ids
            candidates.extend(
                EmployeeProfile.objects.filter(
                    user_id__in=holder_ids, user__is_active=True
                )
                .exclude(user_id__in=already_offered)
                .select_related("user", "team")
            )

        return Response(
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
        """List this team's normal members, or place employees on it.

        GET is the team members screen's roster: every employee whose
        :attr:`EmployeeProfile.team` is this team, with the workflow they are a
        normal member of and whether they also staff a step or hold a team-wide
        role. POST accepts either one ``user`` or a ``users`` list. The list is
        one all-or-nothing write, so a picker that selects several people never
        leaves the roster with only some of them. Both paths apply the same
        guards, so a candidate from another team gets a refusal naming that
        team rather than a silent move.
        """
        team = self.get_object()
        if request.method == "POST":
            bulk = "users" in request.data
            serializer_class = (
                TeamMemberBulkAddSerializer if bulk else TeamMemberAddSerializer
            )
            serializer = serializer_class(
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
        user_id = _positive_int(kwargs["user_id"], "user_id")
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
                pk=_positive_int(workflow_id, "workflow"), team=team
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

    @action(detail=True, methods=["post"], url_path="route")
    def route(self, request, *args, **kwargs):
        """Point this team at one of the chains it owns.

        Routing is a decision about *which* of the team's chains is in force. The
        workflow named must be one the team already owns, so this can only choose
        among the team's own chains — never borrow another team's.
        """
        team = self.get_object()
        workflow_id = request.data.get("workflow")
        workflow = None
        if workflow_id not in (None, ""):
            try:
                workflow_pk = _positive_int(workflow_id, "workflow")
            except ValidationError:
                return Response(
                    {"workflow": ["That workflow is missing or is not this team's."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            workflow = Workflow.objects.filter(pk=workflow_pk, team=team).first()
        try:
            routed = route_team(team=team, actor=request.user, workflow=workflow)
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            TeamSerializer(routed, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_configuration(self, request, *args, **kwargs):
        """Report whether this team's configuration can route, without changing it.

        Side-effect free and available at any status, so HR can check a team that
        is in force and find out which step has lost its approver — the question
        that otherwise only surfaces as a refused submission from the employee.
        A chainless team reports its missing workflow here rather than failing
        silently at submission.
        """
        team = self.get_object()
        readiness = validate_team(team)
        return Response(TeamReadinessSerializer(readiness).data)

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

