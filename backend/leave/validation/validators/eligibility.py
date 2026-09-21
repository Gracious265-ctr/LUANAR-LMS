"""Eligibility rules.

Codes: NOT_ELIGIBLE, ELIGIBILITY_RULE_UNSUPPORTED, ELIGIBILITY_DATA_MISSING.

Rule types (D7): ``gender``, ``min_service``, ``grade_range`` and
``employee_category``. Unknown rule types fail closed; rules that need an
employee attribute the profile lacks also fail closed.
"""

from datetime import date

from ..types import ValidationContext, ValidationIssue


def _whole_months_between(appointment: date, end: date) -> int:
    months = (end.year - appointment.year) * 12 + (end.month - appointment.month)
    if end.day < appointment.day:
        months -= 1
    return months


def validate_eligibility(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the eligibility rules."""
    rules = ctx.leave_type
    if rules is None or not rules.eligibility:
        return [], []

    if ctx.employee is None:
        return [], ["eligibility"]

    issues: list[ValidationIssue] = []
    employee = ctx.employee

    for rule in rules.eligibility:
        rule_type = rule.type
        params = rule.params or {}

        if rule_type == "gender":
            allowed = params.get("allowed") or []
            if employee.gender is None:
                issues.append(_data_missing(rule_type, "gender"))
            elif employee.gender not in allowed:
                issues.append(_not_eligible(rule_type, params))

        elif rule_type == "min_service":
            months = params.get("months")
            if employee.appointment_date is None or months is None:
                issues.append(_data_missing(rule_type, "appointment_date"))
            else:
                service = _whole_months_between(employee.appointment_date, ctx.start_date or ctx.end_date or ctx.today)
                if service < months:
                    issues.append(_not_eligible(rule_type, params))

        elif rule_type == "grade_range":
            min_grade, max_grade = params.get("min"), params.get("max")
            grade = (employee.grade or "").strip().upper()
            if not grade:
                issues.append(_data_missing(rule_type, "grade"))
            elif not (min_grade and max_grade and min_grade <= grade <= max_grade):
                issues.append(_not_eligible(rule_type, params))

        elif rule_type == "employee_category":
            allowed = params.get("allowed") or []
            if employee.category is None:
                issues.append(_data_missing(rule_type, "category"))
            elif employee.category not in allowed:
                issues.append(_not_eligible(rule_type, params))

        else:
            issues.append(
                ValidationIssue(
                    code="ELIGIBILITY_RULE_UNSUPPORTED",
                    field="leave_type",
                    message=(
                        "This leave type uses an unknown eligibility rule "
                        f"({rule_type!r})."
                    ),
                    detail={"rule": rule_type},
                )
            )

    return issues, []


def _not_eligible(rule_type: str, params: dict) -> ValidationIssue:
    return ValidationIssue(
        code="NOT_ELIGIBLE",
        field="leave_type",
        message=f"You are not eligible for this leave type ({rule_type}).",
        detail={"rule": rule_type, "params": params},
    )


def _data_missing(rule_type: str, attribute: str) -> ValidationIssue:
    return ValidationIssue(
        code="ELIGIBILITY_DATA_MISSING",
        field="leave_type",
        message=(
            "Your employee profile is missing data needed to check eligibility "
            f"({rule_type}). Contact HR."
        ),
        detail={"rule": rule_type, "missing": attribute},
    )