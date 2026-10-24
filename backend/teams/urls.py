from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import TeamViewSet

app_name = "teams"

router = SimpleRouter()
router.register("teams", TeamViewSet, basename="team")

urlpatterns = [
    path("", include(router.urls)),
]
