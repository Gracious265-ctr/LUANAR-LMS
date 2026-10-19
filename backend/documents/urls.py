from django.urls import path

from .views import (
    ApprovedDocumentListView,
    ApprovedLeaveDocumentView,
    HRAApprovedLeaveDocumentView,
    LeaveDocumentTemplateView,
    SupportingDocumentListView,
)

app_name = "documents"

urlpatterns = [
    path(
        "leave-document-template/",
        LeaveDocumentTemplateView.as_view(),
        name="leave-document-template",
    ),
    path(
        "documents/supporting/",
        SupportingDocumentListView.as_view(),
        name="documents-supporting",
    ),
    path(
        "documents/approved/",
        ApprovedDocumentListView.as_view(),
        name="documents-approved",
    ),
    path(
        "approved-leave-documents/by-application/<uuid:application_id>/",
        ApprovedLeaveDocumentView.as_view(),
        name="approved-leave-document",
    ),
    path(
        "hr/approved-leave-documents/by-application/<uuid:application_id>/",
        HRAApprovedLeaveDocumentView.as_view(),
        name="hr-approved-leave-document",
    ),
]