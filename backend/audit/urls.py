from rest_framework.routers import SimpleRouter

<<<<<<< HEAD
from .views import AuditEventViewSet, FinalizedLeaveViewSet

router = SimpleRouter()
router.register("audit-entries", AuditEventViewSet, basename="audit-entry")
=======
from .views import AuditEntryViewSet, FinalizedLeaveViewSet

router = SimpleRouter()
router.register("audit-entries", AuditEntryViewSet, basename="audit-entry")
>>>>>>> feature/plans-teams
router.register("finalized-leave", FinalizedLeaveViewSet, basename="finalized-leave")

urlpatterns = router.urls