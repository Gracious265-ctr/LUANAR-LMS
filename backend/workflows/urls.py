from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import DelegationViewSet, WorkflowViewSet

app_name = "workflows"

router = SimpleRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("delegations", DelegationViewSet, basename="delegation")

urlpatterns = [
    path("", include(router.urls)),
]