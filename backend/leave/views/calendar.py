"""Team leave calendar API (UI/UX Phase 2, spec 3.1).

``GET /api/v1/calendar/team/?unit_id={team_id}&month=YYYY-MM`` returns every
approved and pending leave of the team's active members that overlaps the month,
plus the team size and the conflict cap, so the client can both draw the
Gantt-style rows and flag over-subscribed days with the same number the
approval decision enforces (see ``leave.conflicts``).

The "unit" is a :class:`workflows.models.Team` — the spec's fallback grouping,
and the only one this codebase has: ``EmployeeProfile.team`` is what scopes both
approval routing and this calendar, so the two agree by construction. Access is
:func:`workflows.policies.user_can_view_team_calendar`; an unauthorised read is
a 404, never a 403, so a caller cannot probe which teams exist.
"""

from __future__ import annotations

import calendar as _month_calendar
from datetime import date

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import EmployeeProfile
from organisation.models import Team
from workflows.policies import user_can_view_team_calendar

from ..conflicts import COUNTED_STATUSES, conflict_threshold
from ..models import LeaveApplication, LeaveType

_PENDING = "pending"
_APPROVED = "approved"


def _parse_month(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = raw.split("-")
    if len(parts) != 2:
        return None
    try:
        year, month = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (1 <= month <= 12):
        return None
    return year, month


def _positive_int(raw: object) -> int | None:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


class TeamLeaveCalendarView(APIView):
    """One team's leave for one month, scoped to the caller's approval reach."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        parsed = _parse_month(request.query_params.get("month"))
        team_id = _positive_int(request.query_params.get("unit_id"))
        if parsed is None or team_id is None:
            return Response(
                {"detail": "A unit_id and a month (YYYY-MM) are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = Team.objects.filter(pk=team_id).first()
        if team is None or not user_can_view_team_calendar(request.user, team):
            # 404 for both "no such team" and "not yours": the existence of a
            # team is itself information the caller has not earned.
            return Response(
                {"detail": "The calendar does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        year, month = parsed
        first = date(year, month, 1)
        last = date(year, month, _month_calendar.monthrange(year, month)[1])

        team_size = EmployeeProfile.objects.filter(
            team=team, user__is_active=True
        ).count()
        return Response(
            {
                "unit_id": team.pk,
                "unit_name": team.name,
                "month": f"{year:04d}-{month:02d}",
                "team_size": team_size,
                "conflict_threshold": conflict_threshold(team_size),
                "entries": _entries(team, first, last),
            },
            status=status.HTTP_200_OK,
        )


def _entries(team, first: date, last: date) -> list[dict]:
    applications = (
        LeaveApplication.objects.filter(
            employee__employee_profile__team=team,
            status__in=COUNTED_STATUSES,
            start_date__isnull=False,
            end_date__isnull=False,
            start_date__lte=last,
            end_date__gte=first,
        )
        .select_related("employee")
        .order_by("start_date", "employee__first_name", "employee__last_name")
    )
    return [_entry(application) for application in applications]


def _entry(application: LeaveApplication) -> dict:
    employee = application.employee
    return {
        "id": str(application.pk),
        "employee": {
            "id": employee.pk,
            "name": employee.get_full_name() or employee.username,
        },
        "start_date": application.start_date.isoformat(),
        "end_date": application.end_date.isoformat(),
        "leave_type": _leave_type_block(application),
        "status": (
            _APPROVED
            if application.status == LeaveApplication.Status.APPROVED
            else _PENDING
        ),
    }


def _leave_type_block(application: LeaveApplication) -> dict:
    """The application's leave type, from its snapshot then the registry.

    The snapshot is authoritative for a submitted application (the type may have
    been renamed or retired since), so it is read first, exactly as the approver
    review payload does.
    """
    snapshot = (application.rules_snapshot or {}).get("leave_type") or {}
    if snapshot:
        return {
            "id": snapshot.get("id"),
            "code": snapshot.get("code"),
            "name": snapshot.get("name") or "Leave",
        }
    row = LeaveType.objects.filter(pk=application.leave_type_id).first()
    if row is not None:
        return {"id": row.pk, "code": row.code, "name": row.name}
    if application.leave_type_id is None:
        return {"id": None, "code": None, "name": "Leave"}
    return {
        "id": application.leave_type_id,
        "code": None,
        "name": f"Leave type #{application.leave_type_id}",
    }
