from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    EmployeeLeaveTypeViewSet,
    FinancialYearViewSet,
    GradeEntitlementViewSet,
    LeaveApplicationViewSet,
    LeaveRuleViewSet,
    LeaveTypeViewSet,
    PublicHolidayViewSet,
    SupportingDocumentViewSet,
)
from .views.dashboard import LeaveDashboardView
from .views.me import LeaveSummaryView
from .views.resubmit import LeaveApplicationResubmitView
from .views.validation import LeaveApplicationSubmitView, LeaveValidateView

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