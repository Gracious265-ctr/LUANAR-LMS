from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    EmployeeLeaveTypeViewSet,
    FinancialYearViewSet,
    GradeEntitlementViewSet,
    LeaveApplicationViewSet,
    LeaveDocumentConfigView,
    LeaveRuleViewSet,
    LeaveTypeViewSet,
    PublicHolidayViewSet,
    SupportingDocumentViewSet,
)
from .views.me import LeaveSummaryView
from .views.resubmit import LeaveApplicationResubmitView
from .views.validation import LeaveApplicationSubmitView, LeaveValidateView
from .views.my_leave import MyLeaveOverviewView, MyLeaveTypesView
from .views.history import ApplicationHistoryView, MyLeaveHistoryView
from .views.resubmission import (
    ApplicationResubmissionView,
    ApplicationResubmitView,
    ResubmissionDocumentCollectionView,
    ResubmissionDocumentDetailView,
    ResubmissionDocumentReplaceView,
)
from .cancellations.views import (
    CancellationEligibilityView,
    CancelApplicationView,
    CancellationListView,
    CancellationApprovalsListView,
    CancellationDetailView,
    CancellationDecisionView,
)

app_name = "leave"

hr_router = SimpleRouter()
hr_router.register("entitlements", GradeEntitlementViewSet, basename="entitlement")
hr_router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
hr_router.register("leave-rules", LeaveRuleViewSet, basename="leave-rule")
hr_router.register("financial-years", FinancialYearViewSet, basename="financial-year")
hr_router.register("public-holidays", PublicHolidayViewSet, basename="public-holiday")

application_router = DefaultRouter()
application_router.register(
    "leave-applications", LeaveApplicationViewSet, basename="leave-application"
)

supporting_doc_list = SupportingDocumentViewSet.as_view(
    {"get": "list", "post": "create"}
)
supporting_doc_detail = SupportingDocumentViewSet.as_view(
    {"get": "retrieve", "delete": "destroy"}
)
<<<<<<< HEAD
supporting_doc_history = SupportingDocumentViewSet.as_view({"get": "history"})
supporting_doc_replace = SupportingDocumentViewSet.as_view({"post": "replace_document"})
supporting_doc_content = SupportingDocumentViewSet.as_view({"get": "content"})
=======
supporting_doc_replace = SupportingDocumentViewSet.as_view({"post": "replace"})

employee_leave_types = EmployeeLeaveTypeViewSet.as_view({"get": "list"})
>>>>>>> feature/plans-teams

urlpatterns = [
    path(
        "leave/my/overview/",
        MyLeaveOverviewView.as_view(),
        name="leave-my-overview",
    ),
    path(
        "leave/my/history/",
        MyLeaveHistoryView.as_view(),
        name="leave-my-history",
    ),
    path(
        "leave/my/leave-types/",
        MyLeaveTypesView.as_view(),
        name="leave-my-leave-types",
    ),
    path(
        "leave/validate/",
        LeaveValidateView.as_view(),
        name="leave-validate",
    ),
    path(
<<<<<<< HEAD
        "leave-documents/config/",
        LeaveDocumentConfigView.as_view(),
        name="leave-document-config",
=======
        "leave/me/summary/",
        LeaveSummaryView.as_view(),
        name="leave-me-summary",
>>>>>>> feature/plans-teams
    ),
    path(
        "leave-applications/<uuid:pk>/submit/",
        LeaveApplicationSubmitView.as_view(),
        name="leave-application-submit",
    ),
    path(
        "leave-applications/<uuid:pk>/resubmit/",
        LeaveApplicationResubmitView.as_view(),
        name="leave-application-resubmit",
    ),
    path("", include("leave.tracking.urls")),
    path("", include("leave.cancellations.urls")),
    path("", include(hr_router.urls)),
    path("", include(application_router.urls)),
    path(
        "employee/leave-types/",
        employee_leave_types,
        name="employee-leave-type-options",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/",
        supporting_doc_list,
        name="supportingdocument-list",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/history/",
        supporting_doc_history,
        name="supportingdocument-history",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/",
        supporting_doc_detail,
        name="supportingdocument-detail",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/replace/",
        supporting_doc_replace,
        name="supportingdocument-replace",
    ),
<<<<<<< HEAD
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/content/",
        supporting_doc_content,
        name="supportingdocument-content",
    ),
    path(
        "applications/<uuid:pk>/resubmission/",
        ApplicationResubmissionView.as_view(),
        name="application-resubmission",
    ),
    path(
        "applications/<uuid:pk>/history/",
        ApplicationHistoryView.as_view(),
        name="application-history",
    ),
    path(
        "applications/<uuid:pk>/resubmission/documents/",
        ResubmissionDocumentCollectionView.as_view(),
        name="application-resubmission-documents",
    ),
    path(
        "applications/<uuid:pk>/resubmission/documents/<uuid:document_id>/replace/",
        ResubmissionDocumentReplaceView.as_view(),
        name="application-resubmission-document-replace",
    ),
    path(
        "applications/<uuid:pk>/resubmission/documents/<uuid:document_id>/",
        ResubmissionDocumentDetailView.as_view(),
        name="application-resubmission-document-detail",
    ),
    path(
        "applications/<uuid:pk>/resubmit/",
        ApplicationResubmitView.as_view(),
        name="application-resubmit",
    ),
    # Unit 18 - Leave Cancellation
    path(
        "applications/<uuid:pk>/cancellation-eligibility/",
        CancellationEligibilityView.as_view(),
        name="cancellation-eligibility",
    ),
    path(
        "applications/<uuid:pk>/cancel/",
        CancelApplicationView.as_view(),
        name="cancel-application",
    ),
    path(
        "applications/<uuid:pk>/cancellations/",
        CancellationListView.as_view(),
        name="cancellation-list",
    ),
    path(
        "approvals/cancellations/",
        CancellationApprovalsListView.as_view(),
        name="cancellations-approvals-list",
    ),
    path(
        "approvals/cancellations/<int:request_id>/",
        CancellationDetailView.as_view(),
        name="cancellation-detail",
    ),
    path(
        "approvals/cancellations/<int:request_id>/decision/",
        CancellationDecisionView.as_view(),
        name="cancellation-decision",
    ),
=======
>>>>>>> feature/plans-teams
]