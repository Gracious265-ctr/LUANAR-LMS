from django.contrib.auth import authenticate, get_user_model
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import EmployeeProfile
from .permissions import IsHRRole, IsSuperUser
from .serializers import (
    AdminUserSerializer,
    EmployeeSerializer,
    LoginSerializer,
    UserSerializer,
)
from .throttles import LoginRateThrottle

from workflows.models import Team
from workflows.services import wide_approver_ids_for_team

User = get_user_model()


class LoginView(APIView):
    """Authenticate user and return JWT tokens."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class RefreshView(TokenRefreshView):
    """Refresh access token using refresh token."""

    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    """Return the authenticated user's profile."""

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class EmployeeViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for employee records (no hard delete)."""

    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
        "grade",
    ]
    ordering_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
        "grade",
        "appointment_date",
    ]
    ordering = ["user__first_name", "user__last_name"]

    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        team = self.request.query_params.get("team")
        queryset = EmployeeProfile.objects.select_related("user", "team")
        if team:
            # ``team=none`` answers "who is not on a team yet", which the team
            # screen needs to offer candidates; otherwise it is a team id.
            if team == "none":
                queryset = queryset.filter(team__isnull=True)
            else:
                queryset = queryset.filter(team_id=team)

        # A team's roster matches its category: an academic team takes academic
        # employees and an administration team takes administration employees,
        # so the member picker is filtered by the team's own category rather
        # than offering every unassigned employee and refusing the mismatch.
        category = self.request.query_params.get("category")
        if category in EmployeeProfile.Category.values:
            queryset = queryset.filter(category=category)

        # ``not_wide_for_team=<id>`` drops the people who staff the team's steps
        # as wide approvers (institution-wide, team-wide on that team, or
        # campus-wide at its campus): an approver is managed on the Approvers
        # tab, not placed on the roster, so they are offered to nothing here.
        # The same rule the write path enforces, read once for the picker.
        not_wide_for_team = self.request.query_params.get("not_wide_for_team")
        if not_wide_for_team:
            try:
                team_id = int(not_wide_for_team)
            except ValueError:
                team_id = None
            if team_id is not None:
                wide_team = Team.objects.filter(pk=team_id).first()
                if wide_team is not None:
                    queryset = queryset.exclude(
                        user_id__in=wide_approver_ids_for_team(wide_team)
                    )
        return queryset


class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Superuser-only provisioning of HR accounts.

    This is the front door the product was missing: a fresh database has no HR
    user, and without one nobody can reach the HR back office to create the
    campuses, roles, and teams the rest of the app is configured from. The
    superuser (the one account a deployment is bootstrapped with) lists the HR
    accounts here, creates them, resets their password, and activates or
    deactivates them.

    The queryset is fixed to ``role=hr``. The endpoint can neither see nor touch
    ordinary employees or the superusers themselves, so it cannot be turned into
    a general account-minting surface.
    """

    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "first_name", "last_name", "date_joined"]
    ordering = ["first_name", "last_name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.HR).order_by("first_name", "last_name")
