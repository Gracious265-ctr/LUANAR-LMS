from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import ApproverRole, RoleAssignment
from campuses.models import Campus, CampusRoleAssignment
from teams.models import Team, TeamRoleAssignment
from .serializers import (
    ApproverRoleSerializer,
    ApproverRoleWriteSerializer,
    CampusRoleAssignmentSerializer,
    RoleAssignmentSerializer,
    TeamRoleAssignmentSerializer,
)
from .permissions import IsHROnly, IsHROrTeamManager, is_hr
from .services import (
    RoleActionError,
    clear_team_manager,
    deactivate_approver_role,
    managed_team_ids_for,
    remove_campus_role_assignment,
    remove_role_assignment,
    replace_role_assignment,
    set_team_manager,
)

from users.models import User


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Must be an integer."}) from exc
    if parsed < 1:
        raise ValidationError({field_name: "Must be a positive integer."})
    return parsed


class ApproverRoleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for approver roles (no hard delete), plus manager creation.

    Reading, editing, and retiring roles is HR's. *Creating* one is also open to
    a team manager, because a manager describing their own chain may need a role
    that does not exist yet; without it their only route was to ask HR for a
    single word. The service dedupes by name, so the same role cannot be created
    twice and a manager cannot fork the organisation's vocabulary.

    ``DELETE`` maps to :func:`deactivate_approver_role`, which refuses while the
    role is still referenced by an active workflow, a team, or a holder. That is
    why this viewset — unlike the other configuration endpoints — allows DELETE:
    the client sees a 204 for a retired role and a 409 for one still in use.
    """

    permission_classes = [permissions.IsAuthenticated, IsHROnly]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [
                permissions.IsAuthenticated(),
                IsHROrTeamManager(),
            ]
        return [permissions.IsAuthenticated(), IsHROnly()]

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
        # 201 says "this created something"; 200 says "this name already named a
        # role, here it is". A manager adding a role from a chain's step form
        # needs that distinction to avoid claiming a duplicate was made.
        created = getattr(serializer, "role_created", True)
        return Response(
            ApproverRoleSerializer(role, context=self.get_serializer_context()).data,
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
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
    """Institution-wide role holdings: HR writes, managers may read.

    Institution-wide roles need no per-application row: the provider checks
    holders of an active institution-wide role whenever a stage's role has no
    team member. Registrars are the canonical case — a single institution-wide
    registrar handles every leave application.

    Writing a holding stays HR's, because it decides who may act for the whole
    institution. Reading them is open to a team manager as well: the chain form
    a manager may edit shows an institution-wide step's holder by name — and
    locks the step to that person — so refusing the read left the form quietly
    guessing, with a 403 in the server log on every step it drew.
    """

    serializer_class = RoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "list":
            return [permissions.IsAuthenticated(), IsHROrTeamManager()]
        return [permissions.IsAuthenticated(), IsHROnly()]

    def get_queryset(self):
        queryset = RoleAssignment.objects.select_related("user", "role")
        if not is_hr(self.request.user):
            # An institution-wide approver is an administration office, and an
            # academic team may not use one at all. A team manager only sees
            # these holdings when they manage an administration team; handing
            # them to an academic team's chain form would show holders that
            # team's steps can never use.
            manages_administration = Team.objects.filter(
                pk__in=managed_team_ids_for(self.request.user),
                category=Team.Category.ADMINISTRATION,
            ).exists()
            if not manages_administration:
                queryset = queryset.none()
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=_positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=_positive_int(user, "user"))
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

    @action(detail=True, methods=["post"], url_path="replace")
    def replace(self, request, *args, **kwargs):
        """Hand this institution-wide holding to another person (HR only).

        The holder a role has is replaced rather than removed and re-added, so
        the steps and wide memberships the outgoing holder staffed move onto
        their successor in the same step.
        """
        user_id = _positive_int(request.data.get("user"), "user")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"user": ["No such user."]}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            assignment = replace_role_assignment(
                assignment=self.get_object(), user=user, actor=request.user
            )
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            RoleAssignmentSerializer(
                assignment, context=self.get_serializer_context()
            ).data
        )


class TeamRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Team-wide role holdings: HR writes, managers may read their own teams.

    One holder per role per team, and writing a second one replaces the first:
    the screen is a pick-a-role, pick-a-person form, and asking HR to delete
    before they can change their mind is a step that only exists to satisfy the
    database. The service audits both the appointment and the replacement.

    Reading is open to a team manager, scoped to the teams they manage: the
    chain form must show — and lock — a step whose role is held team-wide, and
    without this read a manager's form quietly disagreed with the backend.
    """

    serializer_class = TeamRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "list":
            return [permissions.IsAuthenticated(), IsHROrTeamManager()]
        return [permissions.IsAuthenticated(), IsHROnly()]

    def get_queryset(self):
        queryset = TeamRoleAssignment.objects.select_related(
            "user", "role", "team"
        )
        if not is_hr(self.request.user):
            queryset = queryset.filter(
                team_id__in=managed_team_ids_for(self.request.user)
            )
        team = self.request.query_params.get("team")
        if team:
            queryset = queryset.filter(team_id=_positive_int(team, "team"))
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=_positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=_positive_int(user, "user"))
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
        """Designate a team-wide holding as its team's manager.

        Clears the flag from any other holder on the team, so a team always has
        at most one manager.
        """
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
        """Remove the manager designation from a team-wide holding."""
        try:
            assignment = clear_team_manager(
                assignment=self.get_object(), actor=request.user
            )
        except RoleActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(self.get_serializer(assignment).data)


class CampusRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Campus-wide role holdings: HR writes, managers may read their campuses.

    Scoped to a campus, so the same holding resolves for every team *at* that
    campus and for no team anywhere else. Same one-holder, replace-on-save
    contract as the team-wide holding.

    A manager reads the holdings at the campuses of the teams they manage, so
    the chain form can lock a step to a campus-wide holder it is not allowed to
    change.
    """

    serializer_class = CampusRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "list":
            return [permissions.IsAuthenticated(), IsHROrTeamManager()]
        return [permissions.IsAuthenticated(), IsHROnly()]

    def get_queryset(self):
        queryset = CampusRoleAssignment.objects.select_related(
            "user", "role", "campus"
        )
        if not is_hr(self.request.user):
            campus_ids = (
                Team.objects.filter(
                    pk__in=managed_team_ids_for(self.request.user),
                    campus__isnull=False,
                )
                .values_list("campus_id", flat=True)
                .distinct()
            )
            queryset = queryset.filter(campus_id__in=campus_ids)
        campus = self.request.query_params.get("campus")
        if campus:
            queryset = queryset.filter(campus_id=_positive_int(campus, "campus"))
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role_id=_positive_int(role, "role"))
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=_positive_int(user, "user"))
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
