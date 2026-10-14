"""Dashboard tiering and stat gathering for the system-admin surface.

This module answers two questions for the admin index: *who* is looking (tier)
and, for the developer/ops tier only, *what does the system look like right now*
(stats). The tier gate is applied on the server, so a non-superuser request never
runs the superuser-only ORM queries at all.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Sum
from django.utils import timezone

from audit.models import AuditEntry
from leave.models import LeaveApplication, SupportingDocument
from approvals.models import ApplicationStage

try:  # Django-Q2 ships with the stack; guard so imports stay resilient.
    from django_q.models import Failure, OrmQ, Success
except Exception:  # pragma: no cover - defensive only
    Failure = OrmQ = Success = None

User = get_user_model()

#: The account-management events shown in the "Recent admin actions" panel.
ADMIN_ACTION_EVENTS = (
    AuditEntry.Action.SYSTEM_SUPERUSER_GRANTED,
    AuditEntry.Action.SYSTEM_SUPERUSER_REVOKED,
    AuditEntry.Action.SYSTEM_STAFF_ACCESS_GRANTED,
)

TIER_SUPERUSER = "superuser"
TIER_PLAIN = "plain"


def get_dashboard_tier(user) -> str:
    """Return the dashboard tier for ``user``.

    Only two tiers exist by design: the developer/ops ``superuser`` tier that
    sees the dashboard additions, and ``plain`` for everybody else (including
    HR), who see the stock admin index. There is intentionally no HR tier here.
    """
    return TIER_SUPERUSER if getattr(user, "is_superuser", False) else TIER_PLAIN


def _safe_stat(fn):
    """Evaluate ``fn`` and return ``None`` if the underlying query is unavailable.

    Each stat degrades independently: a missing app or a transient database
    error blanks a single card rather than breaking the whole dashboard.
    """
    try:
        return fn()
    except Exception:
        return None


def _db_size():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        return cursor.fetchone()[0]


def _db_connection_count():
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_stat_activity")
        return cursor.fetchone()[0]


def _task_stats():
    now = timezone.now()
    day_ago = now - timedelta(hours=24)
    return {
        "queued": OrmQ.objects.count(),
        "failed_24h": Failure.objects.filter(stopped__gte=day_ago).count(),
        "succeeded_24h": Success.objects.filter(stopped__gte=day_ago).count(),
    }


def gather_dashboard_stats() -> dict:
    """Return the full stat set. Callers must be superusers.

    Every value is produced through :func:`_safe_stat`, so the return shape is
    stable even when a subsystem is unavailable (that key is simply ``None``).
    """
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    return {
        "users_total": _safe_stat(lambda: User.objects.count()),
        "users_active_30d": _safe_stat(
            lambda: User.objects.filter(
                last_login__gte=now - timedelta(days=30)
            ).count()
        ),
        "applications": _safe_stat(
            lambda: {
                "total": LeaveApplication.objects.count(),
                "pending": LeaveApplication.objects.filter(
                    status=LeaveApplication.Status.SUBMITTED
                ).count(),
                "approved": LeaveApplication.objects.filter(
                    status=LeaveApplication.Status.APPROVED
                ).count(),
                "rejected": LeaveApplication.objects.filter(
                    status=LeaveApplication.Status.REJECTED
                ).count(),
                "submitted_today": LeaveApplication.objects.filter(
                    submitted_at__date=today
                ).count(),
                "submitted_this_week": LeaveApplication.objects.filter(
                    submitted_at__gte=week_ago
                ).count(),
            }
        ),
        "pending_approvals": _safe_stat(
            lambda: ApplicationStage.objects.filter(
                status=ApplicationStage.Status.PENDING
            ).count()
        ),
        "documents": _safe_stat(
            lambda: {
                "active": SupportingDocument.objects.filter(
                    status=SupportingDocument.Status.ACTIVE
                ).count(),
                "storage_bytes": SupportingDocument.objects.filter(
                    status=SupportingDocument.Status.ACTIVE
                ).aggregate(total=Sum("file_size"))["total"]
                or 0,
            }
        ),
        "tasks": _safe_stat(_task_stats),
        "database": _safe_stat(
            lambda: {"size_bytes": _db_size(), "connections": _db_connection_count()}
        ),
    }


def get_recent_admin_actions(limit: int = 20):
    """Return the most recent account-management audit entries, newest first."""
    return list(
        AuditEntry.objects.filter(action__in=ADMIN_ACTION_EVENTS)
        .select_related("actor")
        .order_by("-created_at")[:limit]
    )
