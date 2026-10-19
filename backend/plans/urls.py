from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LeavePlanViewSet, PlanApplyView, PlanScopeOptionsView, TeamPlansView

router = DefaultRouter()
router.register("plans", LeavePlanViewSet, basename="plan")

# The literal custom paths come *before* the router so the router's per-object
# route (``plans/<pk>/``) cannot swallow ``plans/team/`` or
# ``plans/scope-options/`` as a plan id.
urlpatterns = [
    path(
        "plans/scope-options/",
        PlanScopeOptionsView.as_view(),
        name="plan-scope-options",
    ),
    path("plans/team/", TeamPlansView.as_view(), name="plan-team-calendar"),
    path("plans/<uuid:pk>/apply/", PlanApplyView.as_view(), name="plan-apply"),
    path("", include(router.urls)),
]
