from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .approval_views import (
    ApprovalDecisionAPIView,
    ApprovalDetailAPIView,
    ApprovalDocumentDownloadView,
    ApprovalListAPIView,
    ApprovalsCapabilitiesView,
    CancellationDecisionAPIView,
    CancellationDetailAPIView,
    CancellationListAPIView,
)
from .views import (
    ApproverRoleViewSet,
    CampusViewSet,
    DelegationViewSet,
    ReassignmentViewSet,
    RoleAssignmentViewSet,
    TeamMemberViewSet,
    TeamViewSet,
    WorkflowViewSet,
)

app_name = "workflows"

router = SimpleRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("delegations", DelegationViewSet, basename="delegation")
router.register("reassignments", ReassignmentViewSet, basename="reassignment")
router.register("approver-roles", ApproverRoleViewSet, basename="approver-role")
router.register(
    "role-assignments", RoleAssignmentViewSet, basename="role-assignment"
)
router.register("teams", TeamViewSet, basename="team")
router.register("campuses", CampusViewSet, basename="campus")
router.register("team-members", TeamMemberViewSet, basename="team-member")

urlpatterns = [
    path("", include(router.urls)),
    path("approvals/capabilities/", ApprovalsCapabilitiesView.as_view()),
    path(
        "approvals/cancellations/",
        CancellationListAPIView.as_view(),
        name="cancellations-list",
    ),
    path(
        "approvals/cancellations/<str:request_id>/",
        CancellationDetailAPIView.as_view(),
        name="cancellations-detail",
    ),
    path(
        "approvals/cancellations/<str:request_id>/decision/",
        CancellationDecisionAPIView.as_view(),
        name="cancellations-decision",
    ),
    path("approvals/", ApprovalListAPIView.as_view()),
    path("approvals/<str:pk>/", ApprovalDetailAPIView.as_view()),
    path("approvals/<str:pk>/decision/", ApprovalDecisionAPIView.as_view()),
    path(
        "approvals/<str:pk>/documents/<str:document_id>/download-url/",
        ApprovalDocumentDownloadView.as_view(),
    ),
]