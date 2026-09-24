"""Employee-facing "my data" endpoints (Unit 20).

These back the employee dashboard: what the HR-track data actually says about
the signed-in user (profile, annual balance) and what leave types HR has
configured — instead of the placeholder values the dashboard used before.
"""

from datetime import date

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from leave.models import LeaveApplication, LeaveType
from leave.providers.base import LeaveBalanceUnavailableError
from leave.providers import get_provider, get_today

BLOCKING_STATUSES = ("submitted", "pending", "correction_required")


class MyLeaveOverviewView(APIView):
    """Dashboard payload: HR profile, annual balance, application counts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider = get_provider()
        today = get_today()
        user = request.user

        employee = provider.get_employee_for_user(user)
        profile = None
        if employee is not None:
            profile_row = getattr(user, "employee_profile", None)
            profile = {
                "grade": employee.grade,
                "department": profile_row.department if profile_row else "",
                "designation": profile_row.designation if profile_row else "",
                "category": employee.category,
                "gender": employee.gender,
                "appointment_date": employee.appointment_date.isoformat(),
            }

        financial_year = provider.get_financial_year_for(today)
        fiscal = {
            "label": financial_year.label,
            "start": financial_year.start.isoformat(),
            "end": financial_year.end.isoformat(),
        } if financial_year else None

        entitlement = used = available = None
        if employee is not None and financial_year is not None:
            try:
                balance = provider.get_leave_balance(user.id, financial_year.label)
                entitlement, used, available = (
                    balance.entitlement,
                    balance.used,
                    balance.available,
                )
            except LeaveBalanceUnavailableError:
                pass

        pending = LeaveApplication.objects.filter(
            employee=user,
            status__in=BLOCKING_STATUSES,
        ).count()
        upcoming = LeaveApplication.objects.filter(
            employee=user,
            status="approved",
            end_date__gte=today,
        )
        next_leave = (
            upcoming.filter(start_date__gte=today)
            .order_by("start_date")
            .values_list("start_date", flat=True)
            .first()
        )

        return Response(
            {
                "profile": profile,
                "entitlement": entitlement,
                "used": used,
                "available": available,
                "financial_year": fiscal,
                "pending_applications": pending,
                "upcoming_leaves": upcoming.count(),
                "next_leave_start": (
                    next_leave.isoformat() if next_leave else None
                ),
            }
        )


class MyLeaveTypesView(APIView):
    """Leave types HR has configured, with their effective rule hints.

    Only leave types that currently have an effective rule are returned, so
    the application form never offers a type the backend would reject as
    missing/not-yet-effective.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider = get_provider()
        today = get_today()

        items = []
        for leave_type in LeaveType.objects.order_by("name"):
            rules = provider.get_leave_type_rules(leave_type.pk, today)
            if rules is None:
                continue
            items.append(
                {
                    "id": rules.id,
                    "code": rules.code,
                    "name": rules.name,
                    "max_duration_days": rules.max_duration,
                    "requires_supporting_document": rules.requires_document,
                    "consumes_annual_entitlement": rules.deducts_annual_balance,
                    "min_notice_days": rules.min_notice,
                    "eligibility": [
                        {"type": rule.type, "params": rule.params}
                        for rule in rules.eligibility
                    ],
                }
            )
        return Response(items)