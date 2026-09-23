"""Shared types for the leave validation pipeline (Unit 14)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..providers.base import EmployeeInfo, FinancialYear, LeaveTypeRules

# Bumped when a validation rule or snapshot shape changes so historical
# rules_snapshot records can be told apart (invariant 12.5).
VALIDATOR_VERSION = "1"


@dataclass
class ValidationIssue:
    """A single actionable problem found by the validation pipeline.

    ``field`` is a machine-readable target: a form field name (e.g.
    ``"start_date"``, ``"leave_type"``) or ``"—"`` for application-level
    problems. ``message`` is the human-readable backend-authored string the
    frontend renders as-is; ``detail`` carries structured values.
    """

    code: str
    field: str
    message: str
    detail: dict = field(default_factory=dict)


@dataclass
class ValidationContext:
    """Everything a validator needs, collected by the pipeline runner."""

    user: object
    employee: EmployeeInfo | None
    leave_type: LeaveTypeRules | None
    start_date: date | None
    end_date: date | None
    application: object | None
    today: date
    financial_year: FinancialYear | None = None
    holidays: dict[date, str] = field(default_factory=dict)
    working_days: int | None = None
    calendar_days: int | None = None
    available_balance: Decimal | None = None
    balance_after_if_approved: Decimal | None = None
    exclude_application_id: object | None = None


@dataclass
class ValidationResult:
    """The outcome of one ``run_validation`` call."""

    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    skipped_checks: list[str]
    working_days: int | None
    calendar_days: int | None
    financial_year: str | None
    available_balance: Decimal | None
    balance_after_if_approved: Decimal | None
    context: ValidationContext