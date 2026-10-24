from django.urls import include, path
from rest_framework.routers import DefaultRouter

from leave_types.views import LeaveTypeViewSet, grade_options

router = DefaultRouter()
router.register(r"leave-config/types", LeaveTypeViewSet, basename="leave-config-type")

urlpatterns = [
    path("leave-config/grades/", grade_options, name="leave-config-grades"),
    path("", include(router.urls)),
]
