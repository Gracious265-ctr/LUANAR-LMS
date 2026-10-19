from django.urls import path

from .views import (
    ApprovedLeaveDocumentView,
    HRAApprovedLeaveDocumentView,
    LeaveDocumentTemplateView,
    MyApprovedLeaveDocumentsView,
)

app_name = "documents"

urlpatterns = [
    path(
        "leave-document-template/",
        LeaveDocumentTemplateView.as_view(),
        name="leave-document-template",
    ),
    path(
        "approved-leave-documents/",
        MyApprovedLeaveDocumentsView.as_view(),
        name="approved-leave-document-list",
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