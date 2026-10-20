"""Rejected-leave carry-over across a financial-year boundary.

LUANAR carries forward **only** days that a rejection left unused. The product
rules (``context/project-overview.md``) are precise about the two halves:

* "Automatic rejected-leave carry-forward calculation" — a rejected application
  never deducts balance (Invariant 12.4), so its days stay available;
* "No normal unused-leave carry-forward" — entitlement an employee simply did
  not apply for is *not* carried; it resets with the year.

So the amount carried from a closing financial year into the next is bounded on
both sides::

    carried = max(0, min(rejected_days, entitlement_days - consumed_days))

where
``rejected_days``   = working days of the closing year's applications that are
                      *still* in ``rejected`` status at rollover (a rejection
                      that was later resubmitted and approved is no longer
                      rejected, and its days are not carried);
``entitlement_days`` = the grade's annual entitlement resolved for the closing
                      year;
``consumed_days``   = days deducted by approved applications in that year.

The ``min`` is what stops the two rules colliding: a rejection can only carry
what it actually freed up, and never more than the year genuinely had left.

This module is deliberately free of HTTP/auth and is invoked by the
``carry_over_leave`` management command (HR-triggered at rollover), not from any
request path.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum

from . import (
    financial_year_label,
    resolved_annual_entitlement,
)

__all__ = [
    "carry_over_amount",
    "carry_over_financial_year",
    "carry_over_days_for_year",
    "next_financial_year",
]

User = get_user_model()


def carry_over_days_for_year(employee_id: int, financial_year_label: str) -> Decimal:
    """Days carried *into* ``financial_year_label`` for one employee.

    Reads the ``LeaveCarryOver`` rows written at rollover. Absent rows give
    zero, so a year with no rollover reports nothing carried.
    """
    from ..models import LeaveCarryOver

    total = LeaveCarryOver.objects.filter(
        employee_id=employee_id,
        to_financial_year=financial_year_label,
    ).aggregate(total=Sum("days"))["total"]
    return Decimal(total or 0)


def _rejected_days(employee_id: int, label: str) -> Decimal:
    """Working days of the year's applications still rejected at rollover."""
    from ..models import LeaveApplication

    total = LeaveApplication.objects.filter(
        employee_id=employee_id,
        financial_year_label=label,
        status=LeaveApplication.Status.REJECTED,
    ).aggregate(total=Sum("working_days"))["total"]
    return Decimal(total or 0)


def _consumed_days(employee_id: int, label: str) -> Decimal:
    """Days deducted by approved applications in the year (the ledger)."""
    from ..cancellations.models import LeaveBalanceTransaction

    total = LeaveBalanceTransaction.objects.filter(
        employee_id=employee_id,
        financial_year=label,
        type=LeaveBalanceTransaction.Type.DEDUCTION,
    ).aggregate(total=Sum("days"))["total"]
    return Decimal(total or 0)


def _entitlement_days(employee_id: int, closing_year) -> Decimal:
    """The employee's annual entitlement resolved for the closing year."""
    from users.models import EmployeeProfile

    try:
        profile = EmployeeProfile.objects.get(user_id=employee_id)
    except EmployeeProfile.DoesNotExist:
        return Decimal(0)

    entitlement = resolved_annual_entitlement(
        profile.grade, as_of=closing_year.start_date
    )
    return Decimal(entitlement.days) if entitlement is not None else Decimal(0)


def carry_over_amount(employee_id: int, closing_year) -> Decimal:
    """Days eligible to carry from ``closing_year`` into the next year.

    ``closing_year`` is a :class:`~leave.models.FinancialYear`. Returns a
    non-negative ``Decimal``; zero is a legitimate answer (nothing rejected, or
    nothing left unused).
    """
    label = financial_year_label(closing_year)
    rejected = _rejected_days(employee_id, label)
    if rejected <= 0:
        return Decimal(0)

    unused = _entitlement_days(employee_id, closing_year) - _consumed_days(
        employee_id, label
    )
    return max(Decimal(0), min(rejected, unused))


def carry_over_financial_year(
    closing_year, opening_year, *, dry_run: bool = False
):
    """Write carry-over rows from ``closing_year`` into ``opening_year``.

    Iterates every user that had a rejected application in the closing year and
    grants the computed amount as a :class:`~leave.models.LeaveCarryOver` row.
    Idempotent per ``(employee, from, to)``: a re-run updates nothing and writes
    no duplicate, so a command run twice cannot double-grant.

    Returns a list of dicts describing the outcome per employee (``employee``,
    ``days``, ``created``). With ``dry_run=True`` nothing is written.
    """
    from ..models import LeaveApplication, LeaveCarryOver

    from_label = financial_year_label(closing_year)
    to_label = financial_year_label(opening_year)

    rejected_employee_ids = (
        LeaveApplication.objects.filter(
            financial_year_label=from_label,
            status=LeaveApplication.Status.REJECTED,
        )
        .values_list("employee_id", flat=True)
        .distinct()
    )

    results: list[dict] = []
    for employee_id in rejected_employee_ids:
        days = carry_over_amount(employee_id, closing_year)
        if days <= 0:
            continue

        record = {"employee_id": employee_id, "days": days, "created": False}
        if not dry_run:
            with transaction.atomic():
                _, created = LeaveCarryOver.objects.get_or_create(
                    employee_id=employee_id,
                    from_financial_year=from_label,
                    to_financial_year=to_label,
                    defaults={"days": days},
                )
            record["created"] = created
        results.append(record)

    return results


def next_financial_year(closing_year):
    """The configured year starting the day after ``closing_year`` ends, or None.

    Rollover targets the year whose ``start_date`` immediately follows the
    closing year's ``end_date``. Returns ``None`` when no such year is
    configured, so callers can report "no year to roll into" rather than
    silently doing nothing.
    """
    from ..models import FinancialYear

    return (
        FinancialYear.objects.filter(
            start_date=closing_year.end_date + timedelta(days=1)
        )
        .order_by("-start_date")
        .first()
    )
