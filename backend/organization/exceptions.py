"""Errors the organizational tree raises.

Split out from :mod:`organization.models` so a caller can catch a routing
refusal without importing the model module, and so the wording of each refusal
lives in one place next to the condition that raises it.
"""

from __future__ import annotations


class OrganizationError(Exception):
    """Base class for every refusal the organizational tree makes."""


class NoHomeUnitError(OrganizationError):
    """The employee's unit is not bound to the tree, so nothing to escalate to.

    Distinct from :class:`~workflows.providers.WorkflowConfigError` because it
    is not a misconfiguration somebody can fix by editing a section — it is a
    gap in the migration, and the fix is to bind the employee's team or
    department to a unit.
    """


class NoApproverAssignedError(OrganizationError):
    """A unit on the escalation path has nobody to escalate to.

    Carries the unit so the message can name it. That is the whole reason this is
    not a plain string: "no approver" is unactionable, while "the Department of
    Computer Science has no designated approver" tells HR exactly which row of
    the chart to fill in.
    """

    def __init__(self, unit, *, unit_type_label: str = "unit"):
        self.unit = unit
        super().__init__(
            f'The {unit_type_label} "{unit}" has no designated approver, so an '
            "application cannot escalate through it. Appoint somebody in the "
            "organizational chart, or record an acting assignment for the period."
        )


class ChainTooDeepError(OrganizationError):
    """The stored tree is deeper than a real institution can be.

    Almost always a cycle that reached the database through a data migration or a
    script that skipped validation. Refused rather than walked, so a loop can
    never turn one submission into an unbounded walk.
    """


class OrgUnitCycleError(OrganizationError):
    """The stored tree contains a loop and cannot be climbed."""


class ActingAssignmentConflictError(OrganizationError):
    """The requested actancy overlaps one that is already booked for that seat.

    Wraps the existing row so a caller can show HR both bookings side by side
    instead of only a date range.
    """

    def __init__(self, existing):
        self.existing = existing
        if existing.end_date is None:
            period = (
                f"is open-ended from {existing.start_date:%d %b %Y} and so "
                "already covers this period"
            )
        else:
            period = (
                f"already covers {existing.start_date:%d %b %Y} to "
                f"{existing.end_date:%d %b %Y}"
            )
        super().__init__(
            f"{existing} {period}. Two people acting in the same seat is "
            "indistinguishable from nobody knowing who is in charge, so the "
            "overlapping actancy was not recorded. End the existing one first."
        )
