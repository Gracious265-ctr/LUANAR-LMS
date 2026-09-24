from rest_framework.routers import SimpleRouter

from .views import AuditEventViewSet, FinalizedLeaveViewSet

router = SimpleRouter()
router.register("audit-entries", AuditEventViewSet, basename="audit-entry")
router.register("finalized-leave", FinalizedLeaveViewSet, basename="finalized-leave")

urlpatterns = router.urls