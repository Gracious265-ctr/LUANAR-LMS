"""URLs for employee cancellation endpoints (Unit 18)."""

from django.urls import path

from .views import (
    CancelApplicationView,
    CancellationEligibilityView,
    CancellationHistoryView,
)

urlpatterns = [
    path(
        "leave-applications/<uuid:pk>/cancellation-eligibility/",
        CancellationEligibilityView.as_view(),
        name="cancellation-eligibility",
    ),
    path(
        "leave-applications/<uuid:pk>/cancel/",
        CancelApplicationView.as_view(),
        name="application-cancel",
    ),
    path(
        "leave-applications/<uuid:pk>/cancellations/",
        CancellationHistoryView.as_view(),
        name="application-cancellations",
    ),
]