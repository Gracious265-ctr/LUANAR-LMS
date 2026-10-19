"""Employee-facing leave views for the Unit 20 data integration."""

from datetime import timedelta

from django.db.models import Count, Sum
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import LeaveApplication, LeaveRule
from ..providers import get_provider, get_today
from ..services import (
    active_financial_year,
    financial_year_label,
    find_annual_leave_type,
    resolved_annual_entitlement,
)
from ..services.working_days import holidays_in_range
from ..validation.working_days import is_working_day

#: How far ahead the dashboard's "Upcoming Leave" card looks. A rolling window
#: rather than the financial year, so the card answers "what is coming up" and
#: not "what is left of the year" — the balance card already covers the year.
UPCOMING_WINDOW_DAYS = 30

#: How far ahead the form-defaults endpoint looks for public holidays when it
#: finds the first working day. Long enough to clear a weekend plus a run of
#: public holidays, short enough that the holiday lookup never scans a whole year.
DEFAULT_START_HORIZON_DAYS = 31


def _next_working_day(today):
    """Return the first working day strictly after ``today``.

    Skips weekends and configured public holidays (the same provider the
    validation pipeline uses), so the date the form pre-fills is a date the
    submission rules will also accept.
    """
    horizon = today + timedelta(days=DEFAULT_START_HORIZON_DAYS)
    holidays = set(holidays_in_range(today, horizon).keys())
    candidate = today + timedelta(days=1)
    while candidate <= horizon and not is_working_day(candidate, holidays):
        candidate += timedelta(days=1)
    return candidate


class LeaveSummaryView(APIView):
    """Authenticated summary of the employee's leave record and dashboard counts.

    ``GET /api/v1/leave/me/summary/`` returns the employee's profile, resolved
    annual entitlement, active financial year, available balance, and the two
    counts the dashboard cards are built from: applications of theirs that are
    still in motion, and the working days of approved leave falling inside the
    upcoming window. Everything is read from the real HR-track tables, so the
    dashboard reflects exactly what HR manages. Fields degrade to ``None``
    (or ``0`` for the counts) when records or configuration are missing.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        provider = get_provider()

        profile = getattr(user, "employee_profile", None)
        entitlement = None
        if profile is not None:
            entitlement = resolved_annual_entitlement(profile.grade)

        year = active_financial_year()
        year_payload = None
        if year is not None:
            year_payload = {
                "label": financial_year_label(year),
                "start": year.start_date,
                "end": year.end_date,
            }

        available_balance = None
        if profile is not None and year_payload is not None:
            available_balance = provider.get_available_balance(
                user.id, year_payload["label"]
            )

        # Two counts for two dashboard cards. Both are scoped to this employee
        # by construction, so neither can surface anyone else's leave.
        #
        # "Pending" is submitted plus rejected: submitted is waiting on an
        # approver, rejected is waiting on the employee to rework and resubmit
        # (or accept), so neither is finished. Drafts are excluded because
        # nothing has been sent yet.
        today = get_today()
        pending_applications = LeaveApplication.objects.filter(
            employee=user,
            status__in=[
                LeaveApplication.Status.SUBMITTED,
                LeaveApplication.Status.REJECTED,
            ],
        ).count()

        # Only approved leave is scheduled leave, and only if it starts inside
        # the window: leave that has already begun is today, not upcoming.
        # ``calculated_days`` is nullable, so an unfinished row contributes
        # nothing to the sum rather than dragging it to null.
        window_end = today + timedelta(days=UPCOMING_WINDOW_DAYS)
        upcoming = LeaveApplication.objects.filter(
            employee=user,
            status=LeaveApplication.Status.APPROVED,
            start_date__gte=today,
            start_date__lte=window_end,
        ).aggregate(applications=Count("id"), days=Sum("calculated_days"))

        return Response(
            {
                "profile": (
                    {
                        "grade": profile.grade,
                        "category": profile.category,
                        # The name, not the row: this is rendered as JSON.
                        "team": (
                            profile.team.name if profile.team_id else None
                        ),
                        "faculty": profile.faculty,
                        "gender": profile.gender,
                        "appointment_date": profile.appointment_date,
                    }
                    if profile is not None
                    else None
                ),
                "entitlement": (
                    {
                        "days": entitlement.days,
                        "effective_from": entitlement.effective_from,
                    }
                    if entitlement is not None
                    else None
                ),
                "financial_year": year_payload,
                "available_balance": (
                    str(available_balance) if available_balance is not None else None
                ),
                "pending_applications": pending_applications,
                "upcoming_leave": {
                    "days": upcoming["days"] or 0,
                    "applications": upcoming["applications"],
                },
            }
        )


class FormDefaultsView(APIView):
    """Warm-start values for the leave application form.

    ``GET /api/v1/leave/me/form-defaults/`` returns the small set of values the
    form would otherwise guess at: the leave type the employee most recently
    applied for (falling back to the canonical annual type), the first working
    day the form should pre-fill, and the annual entitlement per annual-consuming
    leave type for the active financial year. Everything degrades to ``None`` or
    ``{}`` rather than erroring, because the form reads every field directly.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "employee_profile", None)

        # Most recent live application wins. Cancelled rows are not history the
        # employee wants repeated, and a null type is not a usable default.
        last_leave_type_id = (
            LeaveApplication.objects.filter(employee=user)
            .exclude(status=LeaveApplication.Status.CANCELLED)
            .filter(leave_type_id__isnull=False)
            .order_by("-created_at", "-id")
            .values_list("leave_type_id", flat=True)
            .first()
        )
        if last_leave_type_id is None:
            annual = find_annual_leave_type()
            last_leave_type_id = annual.pk if annual is not None else None

        balance_by_type: dict[str, str] = {}
        if profile is not None and active_financial_year() is not None:
            entitlement = resolved_annual_entitlement(profile.grade)
            if entitlement is not None:
                annual_type_ids = (
                    LeaveRule.objects.filter(
                        consumes_annual_entitlement=True,
                        leave_type__is_active=True,
                    )
                    .values_list("leave_type_id", flat=True)
                    .distinct()
                )
                for type_id in annual_type_ids:
                    if type_id is not None:
                        balance_by_type[str(type_id)] = str(entitlement.days)

        return Response(
            {
                "last_leave_type_id": last_leave_type_id,
                "default_start_date": _next_working_day(get_today()),
                "balance_by_type": balance_by_type,
            }
        )