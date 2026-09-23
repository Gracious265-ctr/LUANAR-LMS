from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .approval_views import (
    ApprovalDecisionAPIView,
    ApprovalDetailAPIView,
    ApprovalDocumentDownloadView,
    ApprovalListAPIView,
    ApprovalsCapabilitiesView,
)
from .views import DelegationViewSet, ReassignmentViewSet, WorkflowViewSet

app_name = "workflows"

router = SimpleRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("delegations", DelegationViewSet, basename="delegation")
router.register("reassignments", ReassignmentViewSet, basename="reassignment")

urlpatterns = [
    path("", include(router.urls)),
    path("approvals/capabilities/", ApprovalsCapabilitiesView.as_view()),
    path("approvals/", ApprovalListAPIView.as_view()),
    path("approvals/<str:pk>/", ApprovalDetailAPIView.as_view()),
    path("approvals/<str:pk>/decision/", ApprovalDecisionAPIView.as_view()),
    path(
        "approvals/<str:pk>/documents/<str:document_id>/download-url/",
        ApprovalDocumentDownloadView.as_view(),
    ),
]