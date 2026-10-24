from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    EmployeeLeaveTypeViewSet,
    FinancialYearViewSet,
    GradeEntitlementViewSet,
    LeaveApplicationViewSet,
    SupportingDocumentViewSet,
)
from .views.dashboard import LeaveDashboardView
from .views.me import LeaveSummaryView
from .views.resubmit import LeaveApplicationResubmitView
from .views.validation import LeaveApplicationSubmitView, LeaveValidateView

app_name = "leave"

hr_router = SimpleRouter()
hr_router.register("entitlements", GradeEntitlementViewSet, basename="entitlement")
hr_router.register("financial-years", FinancialYearViewSet, basename="financial-year")

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
supporting_doc_replace = SupportingDocumentViewSet.as_view({"post": "replace"})

employee_leave_types = EmployeeLeaveTypeViewSet.as_view({"get": "list"})

urlpatterns = [
    path(
        "leave/validate/",
        LeaveValidateView.as_view(),
        name="leave-validate",
    ),
    path(
        "leave/me/summary/",
        LeaveSummaryView.as_view(),
        name="leave-me-summary",
    ),
    path(
        "leave/dashboard/",
        LeaveDashboardView.as_view(),
        name="leave-dashboard",
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
    # Refinement unit 06 retired the HR leave-types CRUD: leave types are now
    # configured in the Leave Configuration app. The endpoint answers with a
    # redirect rather than a 404 so a bookmarked or scripted call still lands
    # somewhere useful.
    path(
        "leave-types/",
        RedirectView.as_view(pattern_name="leave-config-type-list", permanent=False),
        name="legacy-leave-type-list",
    ),
    path(
        "leave-rules/",
        RedirectView.as_view(pattern_name="leave-config-type-list", permanent=False),
        name="legacy-leave-rule-list",
    ),
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
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/",
        supporting_doc_detail,
        name="supportingdocument-detail",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/replace/",
        supporting_doc_replace,
        name="supportingdocument-replace",
    ),
]