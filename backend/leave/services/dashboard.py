"""The Leave app dashboard read model (Unit 3).

Everything the employee's Leave landing page needs, in one call. Two rules
govern this module and nothing else:

- Readers are scoped to ``employee=user`` by construction, so an approver who
  is also an employee never sees anybody else's leave here.
- Balance math is not reimplemented. The annual figure comes from the same
  provider seam the rest of the system uses; the per-type figures are a plain
  sum of that employee's own approved days, which is a read, not a ledger.
"""

from django.db.models import Sum
from django.utils import timezone

from workflows.models import ApprovalDecision

from .. import providers as leave_providers
from ..models import GradeEntitlement, LeaveApplication, LeaveType
from . import (
    active_financial_year,
    financial_year_label,
    grade_in_range,
    normalize_grade,
    resolve_annual_balance_entitlement,
)

#: How much of the latest approver comment the "needs attention" card shows.
EXCERPT_LENGTH = 60

#: At most this many balance rings render; the spec asks for the top few.
MAX_BALANCE_RINGS = 4

#: Section caps (§2.3/§2.6/§2.7).
NEEDS_ATTENTION_LIMIT = 5
DRAFTS_LIMIT = 5
RECENT_LIMIT = 5

#: Backend status -> display status the frontend's status vocabulary uses.
#: ``submitted`` is the model's word; the UI has always called it "pending".
DISPLAY_STATUS = {LeaveApplication.Status.SUBMITTED: "pending"}


def latest_comment_excerpt(application) -> str | None:
    """The latest non-empty approver comment, trimmed to ``EXCERPT_LENGTH``."""
    comment = (
        ApprovalDecision.objects.filter(application=application)
        .exclude(comment="")
        .order_by("-decided_at")
        .values_list("comment", flat=True)
        .first()
    )
    if not comment:
        return None
    text = " ".join(comment.split())
    if len(text) <= EXCERPT_LENGTH:
        return text
    return text[: EXCERPT_LENGTH - 1].rstrip() + "…"


def _leave_type_names(applications) -> dict[int, str]:
    """Map the soft ``leave_type_id``s used by ``applications`` to names."""
    ids = {app.leave_type_id for app in applications if app.leave_type_id}
    if not ids:
        return {}
    return dict(LeaveType.objects.filter(id__in=ids).values_list("id", "name"))


def _serialize_summary(application, leave_type_names, *, include_excerpt=False) -> dict:
    return {
        "id": str(application.id),
        "leave_type": leave_type_names.get(application.leave_type_id),
        "start_date": application.start_date,
        "end_date": application.end_date,
        "status": DISPLAY_STATUS.get(application.status, application.status),
        "updated_at": application.updated_at,
        "created_at": application.created_at,
        "last_comment_excerpt": (
            latest_comment_excerpt(application) if include_excerpt else None
        ),
    }


def _typed_entitlements(grade, as_of):
    """Latest effective typed band per leave type covering ``grade``.

    Returns ``(leave_type, rule)`` pairs, ordered by type name so the rings are
    deterministic before the page caps them.
    """
    key = normalize_grade(grade)
    if key is None:
        return []

    latest: dict[int, GradeEntitlement] = {}
    queryset = GradeEntitlement.objects.filter(
        effective_from__lte=as_of, leave_type__isnull=False
    ).select_related("leave_type")
    for rule in queryset:
        if not grade_in_range(key, rule.grade_start, rule.grade_end):
            continue
        existing = latest.get(rule.leave_type_id)
        if existing is None or rule.effective_from > existing.effective_from:
            latest[rule.leave_type_id] = rule

    return sorted(
        ((rule.leave_type, rule) for rule in latest.values()),
        key=lambda pair: pair[0].name,
    )


def _approved_days_for_type(user, leave_type_id, financial_year_label) -> int:
    """Sum of the employee's approved days of one type in a financial year."""
    if financial_year_label is None:
        return 0
    total = (
        LeaveApplication.objects.filter(
            employee=user,
            status=LeaveApplication.Status.APPROVED,
            leave_type_id=leave_type_id,
            financial_year_label=financial_year_label,
        ).aggregate(total=Sum("calculated_days"))["total"]
    )
    return total or 0


def build_balances(user) -> list[dict]:
    """The annual ring followed by one ring per typed entitlement.

    The annual ring is authoritative and first: its total is the resolved
    annual entitlement and its used is ``total - available`` from the provider
    (the same number the dashboard's stat card has always shown). The per-type
    rings answer "how much sick leave do I have left" and are excluded for the
    annual type itself, which the annual ring already covers.
    """
    profile = getattr(user, "employee_profile", None)
    grade = getattr(profile, "grade", None) if profile else None
    if not grade:
        return []

    as_of = timezone.localdate()
    year = active_financial_year()
    fy_label = financial_year_label(year) if year else None

    rings: list[dict] = []

    annual_rule = resolve_annual_balance_entitlement(grade, as_of)
    if annual_rule is not None and fy_label is not None:
        total = annual_rule.days
        available = leave_providers.get_provider().get_available_balance(
            user.id, fy_label
        )
        used = max(total - int(available), 0)
        label = (
            annual_rule.leave_type.name
            if annual_rule.leave_type_id
            else "Annual Leave"
        )
        rings.append({"leave_type": label, "used": used, "total": total})

    annual_type_id = annual_rule.leave_type_id if annual_rule is not None else None
    for leave_type, rule in _typed_entitlements(grade, as_of):
        if leave_type.pk == annual_type_id:
            continue
        rings.append(
            {
                "leave_type": leave_type.name,
                "used": _approved_days_for_type(user, leave_type.pk, fy_label),
                "total": rule.days,
            }
        )

    # Annual first, then the largest per-type rings.
    if rings:
        annual, rest = rings[0], rings[1:]
        rest.sort(key=lambda ring: ring["total"], reverse=True)
        rings = [annual, *rest]

    return rings[:MAX_BALANCE_RINGS]


def _upcoming_leave(applications, today):
    """The employee's next approved leave, or ``None`` if there is none.

    "Next" is the earliest approved application that has not already started
    (``start_date >= today``): leave beginning today still counts, so the very
    next leave is never hidden, while an in-progress one is not "upcoming".
    """
    application = (
        applications.filter(
            status=LeaveApplication.Status.APPROVED,
            start_date__gte=today,
        )
        .order_by("start_date", "end_date")
        .first()
    )
    if application is None:
        return None
    names = _leave_type_names([application])
    return {
        "id": str(application.id),
        "leave_type": names.get(application.leave_type_id),
        "start_date": application.start_date,
        "end_date": application.end_date,
        "days_until": (application.start_date - today).days,
    }


def get_dashboard_data(user) -> dict:
    """Everything the Leave dashboard renders for ``user``, scoped to them."""
    applications = LeaveApplication.objects.filter(employee=user)
    today = timezone.localdate()

    # Awaiting a decision: submitted and sitting in the approval chain. Every
    # other status is either not yet sent (draft), terminal, or needs the
    # employee (rejected / correction_required), which the needs-attention
    # section already covers.
    pending_count = applications.filter(
        status__in=LeaveApplication.SUBMITTED_STATUSES
    ).count()

    needs_attention = list(
        applications.filter(
            status__in=[
                LeaveApplication.Status.REJECTED,
                LeaveApplication.Status.CORRECTION_REQUIRED,
            ]
        ).order_by("-updated_at")[:NEEDS_ATTENTION_LIMIT]
    )
    drafts = list(
        applications.filter(status=LeaveApplication.Status.DRAFT).order_by(
            "-updated_at"
        )[:DRAFTS_LIMIT]
    )
    recent = list(
        applications.exclude(status=LeaveApplication.Status.DRAFT).order_by(
            "-created_at"
        )[:RECENT_LIMIT]
    )

    names = _leave_type_names([*needs_attention, *drafts, *recent])

    return {
        "balances": build_balances(user),
        "pending_count": pending_count,
        "upcoming_leave": _upcoming_leave(applications, today),
        "needs_attention": [
            _serialize_summary(app, names, include_excerpt=True)
            for app in needs_attention
        ],
        "drafts": [_serialize_summary(app, names) for app in drafts],
        "recent": [_serialize_summary(app, names) for app in recent],
    }
