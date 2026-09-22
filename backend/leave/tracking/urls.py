"""URLs for employee application tracking (Unit 15)."""

from django.urls import path

from .views import ApplicationTrackingView

urlpatterns = [
    path(
        "leave-applications/<uuid:pk>/tracking/",
        ApplicationTrackingView.as_view(),
        name="application-tracking",
    ),
]