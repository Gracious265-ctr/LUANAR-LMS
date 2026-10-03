from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .authentication import assert_token_matches_password
from .models import Department, EmployeeProfile
from .permissions import IsHRRole, IsSuperUser
from .serializers import (
    AdminUserSerializer,
    DepartmentSerializer,
    DepartmentWriteSerializer,
    EmployeeSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordSetConfirmSerializer,
    PasswordSetRequestSerializer,
    PasswordSetValidateSerializer,
    UserSerializer,
)
from .services import (
    GENERIC_REQUEST_RESPONSE,
    DepartmentActionError,
    InvalidPasswordSetToken,
    WrongPasswordError,
    change_password,
    confirm_password_set,
    request_password_set,
    retire_department,
    token_is_usable,
)
from .throttles import (
    LoginRateThrottle,
    PasswordChangeRateThrottle,
    PasswordSetConfirmRateThrottle,
    PasswordSetRequestRateThrottle,
)

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
    """Refresh an access token, refusing one from before a password change.

    ``CHECK_REVOKE_TOKEN`` covers the access path, but not this one:
    ``TokenRefreshView`` hands the raw token to ``TokenRefreshSerializer``, which
    mints a new access token without consulting the user record at all. A refresh
    token captured before a password change would therefore keep working — and
    mint access tokens that pass the access-path check. Since this app neither
    rotates nor blacklists refresh tokens, closing this is the whole of "changing
    my password signs the other devices out".
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        raw = request.data.get("refresh")
        if raw:
            try:
                token = RefreshToken(raw)
            except TokenError:
                # Let the base view produce its own canonical 401 for a malformed
                # or expired token rather than inventing a second error shape.
                return super().post(request, *args, **kwargs)

            user_id = token.payload.get("user_id")
            if user_id is not None:
                user = User.objects.filter(pk=user_id).first()
                if user is not None:
                    assert_token_matches_password(user, token)

        return super().post(request, *args, **kwargs)


class MeView(APIView):
    """Return the authenticated user's profile."""

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class PasswordSetRequestView(APIView):
    """Email a set-password link, or say nothing about whether it was sent.

    ``202`` with one fixed body for every input that is a syntactically valid
    address. Anything else — an unknown address, a deactivated account, an
    account with no email on file — returns exactly the same response, so this
    endpoint cannot be used to enumerate who works here.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordSetRequestRateThrottle]

    def post(self, request):
        serializer = PasswordSetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_password_set(serializer.validated_data["email"])

        return Response(
            {"detail": GENERIC_REQUEST_RESPONSE}, status=status.HTTP_202_ACCEPTED
        )


class PasswordSetValidateView(APIView):
    """Report whether a link is still live, so the page can explain a dead one.

    Separate from confirm so the person sees "this link has expired" instead of
    submitting a password into an error, and so no password is ever posted for a
    token that was never going to work.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        serializer = PasswordSetValidateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        return Response({"valid": token_is_usable(serializer.validated_data["token"])})


class PasswordSetConfirmView(APIView):
    """Set the password behind a live token."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordSetConfirmRateThrottle]

    def post(self, request):
        serializer = PasswordSetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            confirm_password_set(
                serializer.validated_data["token"],
                serializer.validated_data["password"],
            )
        except InvalidPasswordSetToken:
            return Response(
                {
                    "detail": "This link is no longer valid. Ask HR for a new one, "
                    "or request one from the sign-in page."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": [str(message) for message in exc.messages]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deliberately not logged in here: the caller already holds the password,
        # so an automatic session would only add a fixation surface.
        return Response({"detail": "Password set. You can sign in now."})


class PasswordChangeView(APIView):
    """Set a new password for the caller, from a session they already hold.

    Three things happen together here and none of them is optional:

    * the current password is re-checked, so a stolen access token alone cannot
      lock the real owner out of their own account;
    * every other session stops working, because the changed password hash
      invalidates the tokens minted against the old one (see
      :mod:`users.authentication`);
    * the account holder is emailed, so a change they did not make is visible to
      them rather than silent.

    The caller's own token is invalidated too, which is why the frontend clears
    its cookies and sends them back to the sign-in page afterwards.
    """

    throttle_classes = [PasswordChangeRateThrottle]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            change_password(
                user=request.user,
                current_password=serializer.validated_data["current_password"],
                new_password=serializer.validated_data["new_password"],
            )
        except WrongPasswordError:
            return Response(
                {"detail": "Your current password is not correct."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": [str(message) for message in exc.messages]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Password changed. Please sign in again."}
        )


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

    @action(detail=True, methods=["post"], url_path="password-set-link")
    def password_set_link(self, request, pk=None):
        """Reissue the set-password link for one employee's account.

        The first link goes out automatically when HR creates the record; this is
        for the ordinary case of mail that was lost, filtered or read weeks
        later. Issuing a new one invalidates whatever came before, so it doubles
        as "reset their link" without needing a separate endpoint.
        """
        profile = self.get_object()

        if not profile.user.email:
            return Response(
                {"detail": "This employee has no email address to send a link to."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not profile.user.is_active:
            return Response(
                {
                    "detail": "This account is deactivated. Reactivate it before "
                    "sending a password-set link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        request_password_set(profile.user.email, actor=request.user)

        return Response(
            {"detail": f"A password-set link was queued for {profile.user.email}."},
            status=status.HTTP_202_ACCEPTED,
        )


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
