from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    ApprovalDecisionAPIView,
    ApprovalDetailAPIView,
    ApprovalDocumentDownloadView,
    ApprovalListAPIView,
    ApprovalsCapabilitiesView,
    BulkApprovalDecisionAPIView,
    CancellationDecisionAPIView,
    CancellationDetailAPIView,
    CancellationListAPIView,
    DelegationViewSet,
    ReassignmentViewSet,
)

app_name = "approvals"

router = SimpleRouter()
router.register("delegations", DelegationViewSet, basename="delegation")
router.register("reassignments", ReassignmentViewSet, basename="reassignment")

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
    # Registered before the ``<str:pk>`` routes so "bulk-decision" is not
    # parsed as an application id.
    path(
        "approvals/bulk-decision/",
        BulkApprovalDecisionAPIView.as_view(),
        name="approvals-bulk-decision",
    ),
    path("approvals/<str:pk>/", ApprovalDetailAPIView.as_view()),
    path("approvals/<str:pk>/decision/", ApprovalDecisionAPIView.as_view()),
    path(
        "approvals/<str:pk>/documents/<str:document_id>/download-url/",
        ApprovalDocumentDownloadView.as_view(),
    ),
]
