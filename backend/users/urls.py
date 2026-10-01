from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    EmployeeViewSet,
    LoginView,
    MeView,
    PasswordChangeView,
    PasswordSetConfirmView,
    PasswordSetRequestView,
    PasswordSetValidateView,
    RefreshView,
)

app_name = "users"

router = SimpleRouter()
router.register("employees", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    # The one password endpoint that is NOT token-based: the caller is already
    # signed in and proves themselves with their current password instead.
    path(
        "auth/password-change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    # Self-service first password, and the same thing later for a forgotten one.
    path(
        "auth/password-set/request/",
        PasswordSetRequestView.as_view(),
        name="password-set-request",
    ),
    path(
        "auth/password-set/validate/",
        PasswordSetValidateView.as_view(),
        name="password-set-validate",
    ),
    path(
        "auth/password-set/confirm/",
        PasswordSetConfirmView.as_view(),
        name="password-set-confirm",
    ),
    path("", include(router.urls)),
]
