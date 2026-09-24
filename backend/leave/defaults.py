"""Idempotent default HR configuration shared by dev seed commands.

Both ``seed_dev_users`` (user-level seed) and ``seed_approvals_dev`` (approval
scenario seed) run real Unit 14 validation now that the database rules
provider is the default, so the employee side of validation needs real rows to
exist: grade entitlement bands, leave types with effective rules (including
structured eligibility), and a financial year covering today.

These helpers create exactly the defaults that used to live in the fixture
provider, as real ``leave`` model rows. Each is idempotent; the entitlement and
leave-type helpers return how many rows they actually created and the financial
year helper returns ``(year, created)``.
"""

from datetime import date

from django.utils import timezone

from leave.models import FinancialYear, GradeEntitlement, LeaveRule, LeaveType

ENTITLEMENT_BANDS = [
    ("A", "C", 21),
    ("D", "G", 24),
    ("H", "U", 30),
]

DEFAULT_LEAVE_RULES = [
    {
        "code": "annual",
        "name": "Annual leave",
        "max_duration_days": 30,
        "consumes_annual_entitlement": True,
    },
    {
        "code": "maternity",
        "name": "Maternity leave",
        "max_duration_days": 90,
        "eligibility_rules": [
            {"type": "gender", "params": {"allowed": ["F"]}},
        ],
    },
    {
        "code": "paternity",
        "name": "Paternity leave",
        "max_duration_days": 10,
        "eligibility_rules": [
            {"type": "gender", "params": {"allowed": ["M"]}},
        ],
    },
    {
        "code": "compassionate",
        "name": "Compassionate leave",
        "max_duration_days": 5,
    },
]


def ensure_default_entitlements() -> int:
    """Create the default grade/entitlement bands (idempotent). Return created."""
    effective_from = timezone.localdate()
    created = 0
    for grade_start, grade_end, days in ENTITLEMENT_BANDS:
        _, is_new = GradeEntitlement.objects.get_or_create(
            grade_start=grade_start,
            grade_end=grade_end,
            effective_from=effective_from,
            defaults={"days": days},
        )
        created += int(is_new)
    return created


def ensure_default_leave_types_and_rules() -> int:
    """Create built-in leave types and default rules (idempotent). Return created."""
    effective_from = timezone.localdate()
    created = 0
    for item in DEFAULT_LEAVE_RULES:
        leave_type, _ = LeaveType.objects.get_or_create(
            code=item["code"],
            defaults={"name": item["name"]},
        )
        _, is_new = LeaveRule.objects.get_or_create(
            leave_type=leave_type,
            effective_from=effective_from,
            defaults={
                "max_duration_days": item["max_duration_days"],
                "consumes_annual_entitlement": item.get(
                    "consumes_annual_entitlement", False
                ),
                "eligibility_rules": item.get("eligibility_rules", []),
            },
        )
        created += int(is_new)
    return created


def ensure_default_financial_year() -> tuple[FinancialYear, bool]:
    """Create a financial year covering today (idempotent). Return (year, created).

    The year runs 1 July – 30 June around today. ``is_active`` is set only when
    no active financial year exists already.
    """
    today = timezone.localdate()
    existing = FinancialYear.objects.filter(
        start_date__lte=today, end_date__gte=today
    ).first()
    if existing is not None:
        return existing, False
    if today.month >= 7:
        start = date(today.year, 7, 1)
        end = date(today.year + 1, 6, 30)
    else:
        start = date(today.year - 1, 7, 1)
        end = date(today.year, 6, 30)
    year = FinancialYear.objects.create(
        start_date=start,
        end_date=end,
        is_active=not FinancialYear.objects.filter(is_active=True).exists(),
    )
    return year, True