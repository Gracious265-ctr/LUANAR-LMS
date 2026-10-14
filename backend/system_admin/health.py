"""System-health checks for the superuser health panel.

Each check returns a small dict shaped ``{"status": ..., **detail}`` where
``status`` is one of ``ok`` / ``degraded`` / ``down`` / ``unknown``. Checks are
deliberately independent and never raise: a subsystem that is down is reported
as down, not allowed to take the whole page with it.
"""

import time
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from leave.services.storage import ping_storage

try:  # Django-Q2 ships with the stack; guard so imports stay resilient.
    from django_q.models import Success
except Exception:  # pragma: no cover - defensive only
    Success = None

#: A task runner that has not completed any job in this window is degraded.
TASK_RUNNER_STALE_AFTER = timedelta(hours=1)

#: A database round trip slower than this is reported as degraded, not down.
DB_DEGRADED_AFTER_MS = 200


def _check_database() -> dict:
    start = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return {"status": "down", "error": str(exc)}
    latency_ms = round((time.monotonic() - start) * 1000)
    return {
        "status": "ok" if latency_ms < DB_DEGRADED_AFTER_MS else "degraded",
        "latency_ms": latency_ms,
    }


def _check_task_runner() -> dict:
    if Success is None:
        return {"status": "unknown", "detail": "Task runner is not installed"}
    try:
        last_success = Success.objects.order_by("-stopped").first()
    except Exception as exc:
        return {"status": "down", "error": str(exc)}
    if last_success is None:
        return {"status": "unknown", "detail": "No completed tasks yet"}
    stale = (timezone.now() - last_success.stopped) > TASK_RUNNER_STALE_AFTER
    return {
        "status": "degraded" if stale else "ok",
        "last_run": last_success.stopped,
    }


def _check_storage() -> dict:
    try:
        ping_storage()
    except Exception as exc:
        return {"status": "down", "error": str(exc)}
    return {"status": "ok"}


def gather_health_status() -> dict:
    """Run every health check and return the aggregate result."""
    return {
        "database": _check_database(),
        "tasks": _check_task_runner(),
        "storage": _check_storage(),
    }
