"""Organisation HTTP API: approver roles, role holdings, and campuses."""

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.models import User
from users.permissions import IsHRRole

from audit.validation import positive_int

from organisation.models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    RoleAssignment,
)
from organisation.permissions import IsHROnly, IsHROrTeamManager
from organisation.serializers import (
    ApproverRoleSerializer,
    ApproverRoleWriteSerializer,
    CampusRoleAssignmentSerializer,
    CampusSerializer,
    RoleAssignmentSerializer,
)
from organisation.services import (
    CampusActionError,
    RoleActionError,
    deactivate_approver_role,
    remove_campus_role_assignment,
    remove_role_assignment,
    replace_role_assignment,
)

class ApproverRoleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """HR-and-team-manager CRUD for approver roles (no hard delete).

    A team manager may read, create, and edit roles so they can build the
    workflow stages their team needs, but retirement is HR's: ``DELETE`` maps to
    :func:`deactivate_approver_role`, which refuses while the role is still
    referenced by an active workflow, a team, or a holder. The client sees a 204
    for a retired role and a 409 for one still in use.
    """

    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        # Retiring a role is institution-wide surgery, so it stays HR-only even
        # on a viewset a manager may otherwise use.
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsHROnly()]
        return super().get_permissions()

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
    """Institution-wide role holdings.

    Institution-wide roles need no per-application row: the provider checks
    holders of an active institution-wide role whenever a stage's role has no
    team member. Registrars are the canonical case — a single institution-wide
    registrar handles every leave application.

    A team manager may **read** the holdings: their team's chain builder has to
    show an institution-wide step's holder so the role can be filled in. Only HR
    may change a holding.
    """

    serializer_class = RoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        # Reading tells a manager which roles their chain may use; appointing a
        # holder is HR's call, so the writes stay HR-only.
        if self.action in ("create", "destroy", "replace"):
            return [permissions.IsAuthenticated(), IsHROnly()]
        return super().get_permissions()

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

    @action(detail=True, methods=["post"], url_path="replace")
    def replace(self, request, *args, **kwargs):
        """Hand this institution-wide holding to another person (HR only).

        The holder a role has is replaced rather than removed and re-added, so
        the steps and wide memberships the outgoing holder staffed move onto
        their successor in the same step.
        """
        user_id = positive_int(request.data.get("user"), "user")
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


class CampusRoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Campus-wide role holdings.

    Scoped to a campus, so the same holding resolves for every team *at* that
    campus and for no team anywhere else. Same one-holder, replace-on-save
    contract as the team-wide holding. A manager may read the holdings and only
    HR may change one.
    """

    serializer_class = CampusRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [permissions.IsAuthenticated(), IsHROnly()]
        return super().get_permissions()

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
