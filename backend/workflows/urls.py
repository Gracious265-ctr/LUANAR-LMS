from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import DelegationViewSet, ReassignmentViewSet, WorkflowViewSet

app_name = "workflows"

router = SimpleRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("delegations", DelegationViewSet, basename="delegation")
router.register("reassignments", ReassignmentViewSet, basename="reassignment")

urlpatterns = [
    path("", include(router.urls)),
]