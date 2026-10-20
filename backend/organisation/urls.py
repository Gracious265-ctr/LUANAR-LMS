from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    ApproverRoleViewSet,
    CampusRoleAssignmentViewSet,
    CampusViewSet,
    RoleAssignmentViewSet,
)

app_name = "organisation"

router = SimpleRouter()
router.register("approver-roles", ApproverRoleViewSet, basename="approver-role")
router.register(
    "role-assignments", RoleAssignmentViewSet, basename="role-assignment"
)
router.register(
    "campus-role-assignments",
    CampusRoleAssignmentViewSet,
    basename="campus-role-assignment",
)
router.register("campuses", CampusViewSet, basename="campus")

urlpatterns = [
    path("", include(router.urls)),
]
