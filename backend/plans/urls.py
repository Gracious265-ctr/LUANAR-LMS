from django.urls import path

from .views import (
    PlanAdminListAPIView,
    PlanApprovalDecisionAPIView,
    PlanApprovalDetailAPIView,
    PlanApprovalListAPIView,
    PlanBlockConfirmAPIView,
    PlanBlockReleaseAPIView,
    PlanCapabilitiesView,
    PlanDetailAPIView,
    PlanListCreateAPIView,
    PlanPendingConfirmationsAPIView,
    PlanSettingsAPIView,
    PlanSubmitAPIView,
)

app_name = "plans"

urlpatterns = [
    path("plans/capabilities/", PlanCapabilitiesView.as_view()),
    path("plans/settings/", PlanSettingsAPIView.as_view()),
    path("plans/admin/", PlanAdminListAPIView.as_view()),
    path("plans/approvals/", PlanApprovalListAPIView.as_view()),
    path(
        "plans/approvals/<uuid:pk>/decision/",
        PlanApprovalDecisionAPIView.as_view(),
    ),
    path("plans/approvals/<uuid:pk>/", PlanApprovalDetailAPIView.as_view()),
    path(
        "plans/pending-confirmations/",
        PlanPendingConfirmationsAPIView.as_view(),
    ),
    path("plans/<uuid:pk>/submit/", PlanSubmitAPIView.as_view()),
    path(
        "plans/<uuid:pk>/blocks/<uuid:block_id>/confirm/",
        PlanBlockConfirmAPIView.as_view(),
    ),
    path(
        "plans/<uuid:pk>/blocks/<uuid:block_id>/release/",
        PlanBlockReleaseAPIView.as_view(),
    ),
    path("plans/<uuid:pk>/", PlanDetailAPIView.as_view()),
    path("plans/", PlanListCreateAPIView.as_view()),
]