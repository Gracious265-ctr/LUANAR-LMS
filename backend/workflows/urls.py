from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    SectionMemberViewSet,
    WorkflowViewSet,
)

app_name = "workflows"

router = SimpleRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register(
    "section-members", SectionMemberViewSet, basename="section-member"
)

urlpatterns = [
    path("", include(router.urls)),
]
