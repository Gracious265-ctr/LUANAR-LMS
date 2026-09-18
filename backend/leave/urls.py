from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    FinancialYearViewSet,
    GradeEntitlementViewSet,
    LeaveRuleViewSet,
    LeaveTypeViewSet,
    PublicHolidayViewSet,
)

app_name = "leave"

router = SimpleRouter()
router.register("entitlements", GradeEntitlementViewSet, basename="entitlement")
router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("leave-rules", LeaveRuleViewSet, basename="leave-rule")
router.register("financial-years", FinancialYearViewSet, basename="financial-year")
router.register("public-holidays", PublicHolidayViewSet, basename="public-holiday")

urlpatterns = [
    path("", include(router.urls)),
]