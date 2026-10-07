"""Employee-profile services: the team reference and approver eligibility.

Deliberately free of any import from :mod:`workflows`. A team merely *holds* an
employee record, so the dependency between the two apps points
``workflows`` → ``users``, which is the direction Django already applies. A
service here that needed to ask about a team would invert that and make the app
cycle.
"""

from django.db.models import Q


def employee_in_team(employee_profile, team) -> bool:
    """Whether this employee may be appointed on ``team``.

    The team *is* the scope now: an approver must be one of the team's own
    employees. A team with no members yet cannot scope an approver, so nothing is
    eligible — claiming "anybody may approve for an empty team" would make the
    restriction unenforceable the moment HR created the team before hiring
    anybody.
    """
    if team is None or employee_profile is None:
        return False
    return employee_profile.team_id == team.pk


def employee_search_term(term: str) -> Q:
    """Filter matching an employee name loosely, for HR's search box."""
    cleaned = (term or "").strip()
    if not cleaned:
        return Q()
    return (
        Q(user__first_name__icontains=cleaned)
        | Q(user__last_name__icontains=cleaned)
        | Q(user__email__icontains=cleaned)
        | Q(designation__icontains=cleaned)
    )