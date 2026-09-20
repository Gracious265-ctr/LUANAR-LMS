from rest_framework.routers import SimpleRouter

from .views import AuditEntryViewSet, FinalizedLeaveViewSet

router = SimpleRouter()
router.register("audit-entries", AuditEntryViewSet, basename="audit-entry")
router.register("finalized-leave", FinalizedLeaveViewSet, basename="finalized-leave")

urlpatterns = router.urls