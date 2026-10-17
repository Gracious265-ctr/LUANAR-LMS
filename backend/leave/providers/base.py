"""Rules-provider interface for leave validation (Unit 14).

Validators never import the HR-track models (Units 2-5) directly (decision D1).
Instead they depend on this protocol, implemented for now by
:class:`~leave.providers.fixture.FixtureRulesProvider` (placeholder data) and
later swapped for a provider backed by the real models. The swap is one new
class plus a settings change (``LEAVE_RULES_PROVIDER``); the mapping is
documented in ``docs/leave-rules-provider-contract.md`` (Unit 20 handoff).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from typing_extensions import TypeAlias


DurationUnit: TypeAlias = Literal["working_days", "calendar_days"]


@dataclass(frozen=True)
class EmployeeInfo:
    """The employee attributes validation needs from an authenticated user.

    ``appointment_date`` is optional because the column is nullable: a profile
    that exists but has no appointment date still maps to an employee, so the
    run reports ``ELIGIBILITY_DATA_MISSING`` on the rule that needs it rather
    than ``EMPLOYEE_PROFILE_MISSING``, which would deny the profile exists.
    """

    id: int
    user_id: int
    grade: str
    appointment_date: date | None
    category: str | None
    team_id: int | None
    gender: str | None


@dataclass(frozen=True)
class EligibilityRule:
    """A single eligibility rule on a leave type."""

    type: str
    params: dict


@dataclass(frozen=True)
class LeaveTypeRules:
    """The rules of a leave type exactly as evaluated for one application."""

    id: int
    code: str
    name: str
    is_active: bool
    deducts_annual_balance: bool
    max_duration: int | None
    max_duration_unit: DurationUnit
    min_notice: int
    min_notice_unit: DurationUnit
    requires_document: bool
    eligibility: tuple[EligibilityRule, ...]
    effective_from: date


@dataclass(frozen=True)
class FinancialYear:
    """A financial year with an inclusive end date."""

    label: str
    start: date
    end: date


class RulesProvider(Protocol):
    """The interface validation and submission depend on.

    ``get_leave_type_rules`` returns ``None`` for missing, inactive or not-yet-
    effective leave types. ``get_public_holidays`` returns a mapping of date to
    holiday name for the inclusive range, which may be empty.
    """

    def get_employee_for_user(self, user) -> EmployeeInfo | None: ...

    def get_leave_type_rules(
        self, leave_type_id: int, as_of: date
    ) -> LeaveTypeRules | None: ...

    def get_financial_year_for(self, d: date) -> FinancialYear | None: ...

    def get_public_holidays(self, start: date, end: date) -> dict[date, str]: ...

    def get_available_balance(
        self, employee_id: int, financial_year_label: str
    ) -> Decimal: ...