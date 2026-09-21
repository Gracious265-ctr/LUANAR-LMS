"""PLACEHOLDER fixture data for the Unit 14 rules provider.

This module exists only so the leave flow works standalone before the HR-track
models are merged. It is deliberately NOT authoritative: the financial year
dates, public holidays, leave-type rules and balances below are invented
placeholders. Tests never depend on it (they inject a stub provider), and the
real provider swap is documented in ``docs/leave-rules-provider-contract.md``.
"""

from datetime import date

from .base import EligibilityRule, FinancialYear, LeaveTypeRules

# Financial year 2026-27 (placeholder; not confirmed as LUANAR's actual year).
FINANCIAL_YEARS = (
    FinancialYear(label="2026-27", start=date(2026, 7, 1), end=date(2027, 6, 30)),
)

# A few arbitrary public holidays (placeholder).
PUBLIC_HOLIDAYS: dict[date, str] = {
    date(2026, 9, 30): "Placeholder Public Holiday",
    date(2026, 12, 25): "Placeholder Christmas Day",
    date(2026, 12, 26): "Placeholder Boxing Day",
    date(2027, 1, 1): "Placeholder New Year's Day",
}

# Annual entitlement by grade (from the project overview). Fixture balances
# equal the entitlement with no deductions.
GRADE_ANNUAL_ENTITLEMENT = {
    ("A", "C"): 21,
    ("D", "G"): 24,
    ("H", "U"): 30,
}

# Leave types (placeholder rules; notice/max values beyond the confirmed ones
# below are invented). IDs align with the frontend leave-type mock list.
LEAVE_TYPES: tuple[LeaveTypeRules, ...] = (
    LeaveTypeRules(
        id=1,
        code="annual",
        name="Annual Leave",
        is_active=True,
        deducts_annual_balance=True,
        max_duration=None,
        max_duration_unit="working_days",
        min_notice=5,
        min_notice_unit="working_days",
        requires_document=False,
        eligibility=(),
        effective_from=date(2026, 1, 1),
    ),
    LeaveTypeRules(
        id=2,
        code="maternity",
        name="Maternity Leave",
        is_active=True,
        deducts_annual_balance=False,
        max_duration=90,
        max_duration_unit="calendar_days",
        min_notice=0,
        min_notice_unit="working_days",
        requires_document=True,
        eligibility=(EligibilityRule("gender", {"allowed": ["F"]}),),
        effective_from=date(2026, 1, 1),
    ),
    LeaveTypeRules(
        id=3,
        code="paternity",
        name="Paternity Leave",
        is_active=True,
        deducts_annual_balance=False,
        max_duration=10,
        max_duration_unit="calendar_days",
        min_notice=0,
        min_notice_unit="working_days",
        requires_document=False,
        eligibility=(EligibilityRule("gender", {"allowed": ["M"]}),),
        effective_from=date(2026, 1, 1),
    ),
    LeaveTypeRules(
        id=4,
        code="compassionate",
        name="Compassionate Leave",
        is_active=True,
        deducts_annual_balance=False,
        max_duration=5,
        max_duration_unit="working_days",
        min_notice=0,
        min_notice_unit="calendar_days",
        requires_document=False,
        eligibility=(),
        effective_from=date(2026, 1, 1),
    ),
)

# Seeded dev users resolved by username; unknown usernames return None.
EMPLOYEES: dict[str, dict] = {
    "employee@test.luanar": {
        "grade": "B",
        "appointment_date": date(2022, 3, 15),
        "category": "administration",
        "gender": "F",
    },
    "supervisor@test.luanar": {
        "grade": "E",
        "appointment_date": date(2018, 9, 1),
        "category": "academic",
        "gender": "M",
    },
    "hod@test.luanar": {
        "grade": "G",
        "appointment_date": date(2015, 1, 10),
        "category": "academic",
        "gender": "M",
    },
    "dean@test.luanar": {
        "grade": "H",
        "appointment_date": date(2012, 6, 1),
        "category": "academic",
        "gender": "M",
    },
    "registrar@test.luanar": {
        "grade": "H",
        "appointment_date": date(2010, 8, 15),
        "category": "administration",
        "gender": "F",
    },
    "dvc@test.luanar": {
        "grade": "H",
        "appointment_date": date(2008, 4, 1),
        "category": "administration",
        "gender": "F",
    },
    "hr@test.luanar": {
        "grade": "E",
        "appointment_date": date(2019, 2, 1),
        "category": "administration",
        "gender": "F",
    },
}


def annual_entitlement_for_grade(grade: str) -> int | None:
    """Return the fixture annual entitlement for a grade letter, or None."""
    grade = (grade or "").strip().upper()
    for (start, end), days in GRADE_ANNUAL_ENTITLEMENT.items():
        if start <= grade <= end:
            return days
    return None