from rest_framework import mixins, permissions, viewsets
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
from .permissions import IsHROnly, is_hr

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
    """HR-only CRUD for approver roles (no hard delete).

    ``DELETE`` maps to :func:`deactivate_approver_role`, which refuses while the
    role is still referenced by an active workflow, a team, or a holder. That is
    why this viewset — unlike the other configuration endpoints — allows DELETE:
    the client sees a 204 for a retired role and a 409 for one still in use.
    """

    permission_classes = [permissions.IsAuthenticated, IsHROnly]
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
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
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
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
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
    """Campus-wide role holdings (HR only).

    Scoped to a campus, so the same holding resolves for every team *at* that
    campus and for no team anywhere else. Same one-holder, replace-on-save
    contract as the team-wide holding.
    """

    serializer_class = CampusRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
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
