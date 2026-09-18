from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import EmployeeViewSet, LoginView, MeView, RefreshView

app_name = "users"

router = SimpleRouter()
router.register("employees", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]