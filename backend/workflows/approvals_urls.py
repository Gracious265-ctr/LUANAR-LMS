from django.urls import path

from .approvals_views import (
    ApprovalCapabilitiesView,
    ApprovalDecisionView,
    ApprovalDetailView,
    ApprovalDocumentDownloadView,
    ApprovalListView,
)

app_name = "approvals"

urlpatterns = [
    path("approvals/capabilities/", ApprovalCapabilitiesView.as_view(), name="capabilities"),
    path("approvals/", ApprovalListView.as_view(), name="list"),
    path(
        "approvals/<uuid:application_id>/",
        ApprovalDetailView.as_view(),
        name="detail",
    ),
    path(
        "approvals/<uuid:application_id>/decision/",
        ApprovalDecisionView.as_view(),
        name="decision",
    ),
    path(
        "approvals/<uuid:application_id>/documents/<uuid:document_id>/download-url/",
        ApprovalDocumentDownloadView.as_view(),
        name="document-download-url",
    ),
]