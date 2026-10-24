from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    ApproverRoleViewSet,
    RoleAssignmentViewSet,
    TeamRoleAssignmentViewSet,
)

app_name = "roles"

router = SimpleRouter()
router.register("approver-roles", ApproverRoleViewSet, basename="approver-role")
router.register("role-assignments", RoleAssignmentViewSet, basename="role-assignment")
router.register(
    "team-role-assignments",
    TeamRoleAssignmentViewSet,
    basename="team-role-assignment",
)

urlpatterns = [
    path("", include(router.urls)),
]
