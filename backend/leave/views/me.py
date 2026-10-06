"""Employee-facing leave views for the Unit 20 data integration."""

from datetime import timedelta

from django.db.models import Count, Sum
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import LeaveApplication
from ..providers import get_provider, get_today
from ..services import active_financial_year, financial_year_label, resolved_annual_entitlement

#: How far ahead the dashboard's "Upcoming Leave" card looks. A rolling window
#: rather than the financial year, so the card answers "what is coming up" and
#: not "what is left of the year" — the balance card already covers the year.
UPCOMING_WINDOW_DAYS = 30


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
        # "Pending" is submitted plus correction-required: the two statuses in
        # which the application is waiting on a person rather than finished.
        # Drafts are excluded because nothing has been sent yet.
        today = get_today()
        pending_applications = LeaveApplication.objects.filter(
            employee=user,
            status__in=[
                LeaveApplication.Status.SUBMITTED,
                LeaveApplication.Status.CORRECTION_REQUIRED,
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
                        "department": (
                            profile.department.name
                            if profile.department_id
                            else None
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