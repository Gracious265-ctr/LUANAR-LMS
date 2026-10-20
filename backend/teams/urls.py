from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import TeamRoleAssignmentViewSet, TeamViewSet

app_name = "teams"

router = SimpleRouter()
router.register("teams", TeamViewSet, basename="team")
router.register(
    "team-role-assignments",
    TeamRoleAssignmentViewSet,
    basename="team-role-assignment",
)

urlpatterns = [
    path("", include(router.urls)),
]
