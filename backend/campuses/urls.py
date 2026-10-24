from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CampusViewSet
from roles.views import CampusRoleAssignmentViewSet

app_name = "campuses"

router = SimpleRouter()
router.register("campuses", CampusViewSet, basename="campus")
router.register(
    "campus-role-assignments",
    CampusRoleAssignmentViewSet,
    basename="campus-role-assignment",
)

urlpatterns = [
    path("", include(router.urls)),
]
