"""Writes to the organizational tree, and the home-unit resolver.

Two responsibilities live here rather than on the models:

* :func:`resolve_home_unit` — the one place that answers "where does this
  employee sit", so the chain resolver, the HR screens, and the reporting views
  cannot each invent their own answer.
* :func:`create_acting_assignment` — overlap checking that survives two HR users
  pressing save at the same time. ``Model.clean()`` cannot do that; it sees one
  row.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from organization.exceptions import ActingAssignmentConflictError, NoHomeUnitError
from organization.models import ActingAssignment, OrgUnit


def resolve_home_unit(employee) -> OrgUnit | None:
    """The organizational unit an employee's approvals start from.

    Derived, never stored. ``EmployeeProfile`` already holds exactly one ``team``
    and one ``department`` as single-valued foreign keys, so the answer is always
    available by reading two columns — and caching it in a third would create a
    value that disagrees with the other two the first time somebody changes
    team.

    Team wins over department because a team is the finer unit: an employee in a
    team escalates from the team, and only an employee with no team escalates
    from their department. Returns ``None`` when neither is bound to the tree,
    which is every employee until HR has migrated their unit — the caller
    decides whether that means "use the hand-configured chain" or "refuse".
    """
    profile = getattr(employee, "employee_profile", None)
    if profile is None:
        return None

    team = getattr(profile, "team", None)
    if team is not None and team.org_unit_id:
        return team.org_unit

    department = getattr(profile, "department", None)
    if department is not None and department.org_unit_id:
        return department.org_unit

    return None


def require_home_unit(employee) -> OrgUnit:
    """Like :func:`resolve_home_unit` but refuses rather than returning ``None``.

    Used by the tree resolver, where a missing home unit is a refusal to route
    and not a reason to fall back to a chain built for a different shape of
    institution.
    """
    unit = resolve_home_unit(employee)
    if unit is None:
        raise NoHomeUnitError(
            "This employee's home unit is not set up in the organizational tree "
            "yet, so there is nobody for their application to escalate to. Ask "
            "HR to put their team or department on the chart."
        )
    return unit


def unit_chain_to_root(unit: OrgUnit) -> list[OrgUnit]:
    """The escalation path from ``unit`` up to the apex, nearest first.

    Inactive units are included, not filtered: the path a historical application
    took is part of its record. Callers deciding what to route *now* filter
    afterwards.
    """
    return list(unit.ancestors(include_self=True))


def covering_acting_assignment(
    unit: OrgUnit, on: date | None = None
) -> ActingAssignment | None:
    """The actancy covering ``unit`` on ``on``, if any.

    A role-scoped actancy and a person-scoped actancy cover different seats, so
    both are candidates; ordered by ``start_date`` descending so the most
    recently booked one wins if bad data ever leaves two matching. This mirrors
    ``Delegation.state``: the answer is derived from the dates on read, never
    cached in a column a midnight rollover could leave stale.
    """
    day = on or timezone.localdate()
    return (
        ActingAssignment.objects.filter(org_unit=unit)
        .filter(start_date__lte=day)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=day))
        .order_by("-start_date", "-pk")
        .first()
    )


@transaction.atomic
def create_acting_assignment(
    *,
    org_unit: OrgUnit,
    actor,
    start_date: date,
    acting_user=None,
    end_date: date | None = None,
    role=None,
    reason: str = "",
) -> ActingAssignment:
    """Record an actancy, refusing one that overlaps an existing actancy.

    The overlap test is run twice on purpose. ``ActingAssignment.clean()``
    catches the case where a single user is configuring, and this re-runs it
    inside a transaction with the unit's rows locked — two HR users booking the
    same seat a second apart would both pass a plain ``exists()`` check and then
    both write. Locking the org unit row serialises them, so the second one sees
    the first one's insert and is refused instead of leaving the seat ambiguous.

    Nothing is written on conflict and no audit entry is recorded: the caller's
    whole transaction fails, so a refused booking leaves no trace that could be
    mistaken for a successful one.
    """
    if role is None and acting_user is None:
        raise ValueError("An acting assignment needs a person or a role.")
    if role is not None and acting_user is not None:
        raise ValueError(
            "An acting assignment covers either a person or a role, not both."
        )

    # Serialise every booking for this unit behind the unit row.
    locked = OrgUnit.objects.select_for_update().get(pk=org_unit.pk)

    # A role-scoped actancy and a person-scoped actancy occupy different seats,
    # so they only conflict with their own kind.
    if role is not None:
        existing_rows = ActingAssignment.objects.select_for_update().filter(
            org_unit=locked, role=role
        )
    else:
        existing_rows = ActingAssignment.objects.select_for_update().filter(
            org_unit=locked, role__isnull=True
        )

    candidate = ActingAssignment(
        org_unit=locked,
        role=role,
        acting_user=acting_user,
        start_date=start_date,
        end_date=end_date,
    )
    for existing in existing_rows:
        if existing.overlaps(candidate):
            raise ActingAssignmentConflictError(existing)

    return ActingAssignment.objects.create(
        org_unit=locked,
        role=role,
        acting_user=acting_user,
        start_date=start_date,
        end_date=end_date,
        reason=(reason or "").strip(),
        created_by=actor,
    )
