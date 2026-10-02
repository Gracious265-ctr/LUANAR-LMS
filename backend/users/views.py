from django.contrib.auth import authenticate, get_user_model
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Department, EmployeeProfile
from .permissions import IsHRRole, IsSuperUser
from .serializers import (
    AdminUserSerializer,
    DepartmentSerializer,
    DepartmentWriteSerializer,
    EmployeeSerializer,
    LoginSerializer,
    UserSerializer,
)
from .services import DepartmentActionError, retire_department
from .throttles import LoginRateThrottle

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
        "department__name",
        "grade",
    ]
    ordering_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
        "department__name",
        "grade",
        "appointment_date",
    ]
    ordering = ["user__first_name", "user__last_name"]

    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        department = self.request.query_params.get("department")
        team = self.request.query_params.get("team")
        queryset = EmployeeProfile.objects.select_related("user", "department", "team")
        if department:
            queryset = queryset.filter(department_id=department)
        if team:
            # ``team=none`` answers "who is not on a team yet", which the team
            # screen needs to offer candidates; otherwise it is a team id.
            if team == "none":
                queryset = queryset.filter(team__isnull=True)
            else:
                queryset = queryset.filter(team_id=team)
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
    departments, roles, and teams the rest of the app is configured from. The
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


class DepartmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for departments (no hard delete).

    Read and write go through separate serializers because the two answer
    different questions: the read shape carries the teams and employee count a
    department screen displays, and the write shape carries only the name that
    HR is allowed to set.
    """

    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Department.objects.prefetch_related("teams")
        if self.request.query_params.get("include_retired") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DepartmentWriteSerializer
        return DepartmentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            department = serializer.save()
        except DepartmentActionError as exc:
            raise ValidationError({exc.field: [exc.message]}) from exc
        return Response(
            DepartmentSerializer(department).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            department = serializer.save()
        except DepartmentActionError as exc:
            raise ValidationError({exc.field: [exc.message]}) from exc
        return Response(DepartmentSerializer(department).data)

    @action(detail=True, methods=["post"])
    def retire(self, request, pk=None):
        """Retire a department; it cannot be deleted while anything uses it."""
        department = self.get_object()
        try:
            department = retire_department(
                department=department, actor=request.user
            )
        except DepartmentActionError as exc:
            raise ValidationError({exc.field: [exc.message]}) from exc
        return Response(DepartmentSerializer(department).data)