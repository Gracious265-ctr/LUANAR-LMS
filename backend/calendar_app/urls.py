from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    CalendarEventViewSet,
    FinancialYearViewSet,
    HolidayViewSet,
    WorkingDaysView,
)

app_name = "calendar_app"

router = SimpleRouter()
router.register("financial-years", FinancialYearViewSet, basename="financial-year")
router.register("holidays", HolidayViewSet, basename="holiday")
router.register("events", CalendarEventViewSet, basename="event")

urlpatterns = [
    path("calendar/", include(router.urls)),
    path("calendar/working-days/", WorkingDaysView.as_view(), name="working-days"),
]
