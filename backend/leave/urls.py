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
]