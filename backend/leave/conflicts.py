"""Team-overlap conflict rule (UI/UX Phase 2, spec 3.2 + scoping decision).

"Too many people off at once" is one number with two readers:

* the **calendar** flags a day the team is already over-subscribed on, so an
  approver can see the shape of the month before deciding; and
* the **approval decision** refuses an ``approve`` that would leave the team
  over-subscribed on any day — a hard block, enforced at every stage and
  backend-authoritative, rather than a visual hint the client may skip.

Both read the numbers from here, so the flag the approver sees and the refusal
the server enforces can never disagree. The cap is
``max(1, ceil(0.3 × active team size))`` simultaneously-out people — "more than
30% of the team" — which for a team of five is two people, so a third concurrent
absence is the conflict the spec's example describes.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from users.models import EmployeeProfile

from .models import LeaveApplication

#: Fraction of a team that may be out on one day without counting as a conflict.
CONFLICT_RATIO = 0.3

#: A day counts people who are away *or may be*: an approved application is
#: certain, a submitted one is not yet refused, and treating it as absent is the
#: conservative reading the approver needs. Drafts, rejections and cancellations
#: are not "out" and are excluded.
COUNTED_STATUSES = (
    LeaveApplication.Status.SUBMITTED,
    LeaveApplication.Status.APPROVED,
)


@dataclass(frozen=True)
class TeamConflict:
    """The first day an approval would over-subscribe the applicant's team."""

    day: date
    out_count: int
    team_size: int
    threshold: int


def conflict_threshold(team_size: int) -> int:
    """The most people who may be out at once without a conflict.

    Always at least one, so a team of one or two can never be "conflicted" by
    arithmetic alone.
    """
    if team_size <= 0:
        return 1
    return max(1, math.ceil(CONFLICT_RATIO * team_size))


def _active_team_size(team) -> int:
    return EmployeeProfile.objects.filter(
        team=team, user__is_active=True
    ).count()


def _overlapping_counts(*, team, start, end, exclude_pk) -> Counter:
    """Per-day headcount of counted leave overlapping ``[start, end]``.

    Only the days inside the window are tallied; a leave that runs past the
    window contributes nothing outside it. ``exclude_pk`` drops one application
    so a caller can ask what the day looks like *besides* the one in hand.
    """
    rows = (
        LeaveApplication.objects.filter(
            employee__employee_profile__team=team,
            status__in=COUNTED_STATUSES,
            start_date__isnull=False,
            end_date__isnull=False,
            start_date__lte=end,
            end_date__gte=start,
        )
        .exclude(pk=exclude_pk)
        .values_list("start_date", "end_date")
    )
    counts: Counter = Counter()
    for row_start, row_end in rows:
        first = row_start if row_start > start else start
        last = row_end if row_end < end else end
        day = first
        while day <= last:
            counts[day] += 1
            day += timedelta(days=1)
    return counts


def find_team_conflict(application, *, team=None) -> TeamConflict | None:
    """Whether approving ``application`` would conflict, and the first such day.

    Counts the application itself on top of the other counted leave already
    overlapping its window, so the answer is "the total if this one were also
    out". Returns ``None`` when the employee has no team, no dates, a team of one
    or fewer, or when every day stays within the cap.
    """
    if application.start_date is None or application.end_date is None:
        return None
    if team is None:
        profile = getattr(application.employee, "employee_profile", None)
        team = profile.team if profile is not None else None
    if team is None:
        return None

    team_size = _active_team_size(team)
    if team_size <= 1:
        return None
    threshold = conflict_threshold(team_size)

    counts = _overlapping_counts(
        team=team,
        start=application.start_date,
        end=application.end_date,
        exclude_pk=application.pk,
    )
    day = application.start_date
    while day <= application.end_date:
        total = counts[day] + 1
        if total > threshold:
            return TeamConflict(
                day=day,
                out_count=total,
                team_size=team_size,
                threshold=threshold,
            )
        day += timedelta(days=1)
    return None
