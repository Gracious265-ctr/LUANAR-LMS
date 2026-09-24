from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    FinancialYearViewSet,
    GradeEntitlementViewSet,
    LeaveApplicationViewSet,
    LeaveRuleViewSet,
    LeaveTypeViewSet,
    PublicHolidayViewSet,
    SupportingDocumentViewSet,
)
from .views.validation import LeaveApplicationSubmitView, LeaveValidateView
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

urlpatterns = [
    path(
        "leave/validate/",
        LeaveValidateView.as_view(),
        name="leave-validate",
    ),
    path(
        "leave-applications/<uuid:pk>/submit/",
        LeaveApplicationSubmitView.as_view(),
        name="leave-application-submit",
    ),
    path("", include("leave.tracking.urls")),
    path("", include(hr_router.urls)),
    path("", include(application_router.urls)),
    path(
        "leave-applications/<uuid:application_pk>/documents/",
        supporting_doc_list,
        name="supportingdocument-list",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/",
        supporting_doc_detail,
        name="supportingdocument-detail",
    ),
    path(
        "applications/<uuid:pk>/resubmission/",
        ApplicationResubmissionView.as_view(),
        name="application-resubmission",
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
]