"""``get_entitlement`` reads the provider-backed grade/type/year mapping.

The contract: configured rows answer with their days; every unresolved step
— no provider record, no grade, no row, no financial year — is ``None``, so
the dashboard omits the ring instead of showing a false zero.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from leave.models import FinancialYear, GradeLeaveEntitlement
from leave_types.models import LeaveType
from leave.services import get_entitlement

User = get_user_model()

#: Fixture-directory identities (directory/fixtures/seed_data.json).
ADMIN_EMAIL = "admin@test.luanar"  # EMP-001, grade G
EMPLOYEE_TWO_EMAIL = "employee2@test.luanar"  # EMP-005, grade B
ADMIN_GRADE_ID = "G"
EMPLOYEE_TWO_GRADE_ID = "B"


class GetEntitlementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=ADMIN_EMAIL, email=ADMIN_EMAIL, password="pass"
        )
        self.year = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )
        self.sick = LeaveType.objects.create(name="Sick Leave", code="sick")
        self.compassionate = LeaveType.objects.create(
            name="Compassionate Leave", code="compassionate"
        )

    def grant(self, *, grade_id=ADMIN_GRADE_ID, leave_type=None, days=10, year=None):
        return GradeLeaveEntitlement.objects.create(
            grade_id=grade_id,
            leave_type=leave_type or self.sick,
            financial_year=year or self.year,
            days=days,
        )

    def test_configured_mapping_returns_the_days(self):
        self.grant(days=7)

        self.assertEqual(get_entitlement(self.user, self.sick, self.year), 7)

    def test_unconfigured_leave_type_returns_none(self):
        self.grant(days=7)

        self.assertIsNone(
            get_entitlement(self.user, self.compassionate, self.year)
        )

    def test_unconfigured_grade_returns_none(self):
        self.grant(grade_id=ADMIN_GRADE_ID, days=7)
        other = User.objects.create_user(
            username=EMPLOYEE_TWO_EMAIL, email=EMPLOYEE_TWO_EMAIL, password="pass"
        )

        self.assertIsNone(get_entitlement(other, self.sick, self.year))

    def test_unconfigured_financial_year_returns_none(self):
        self.grant(days=7)
        other_year = FinancialYear.objects.create(
            start_date=date(2025, 7, 1), end_date=date(2026, 6, 30)
        )

        self.assertIsNone(get_entitlement(self.user, self.sick, other_year))

    def test_user_without_a_provider_record_returns_none(self):
        stranger = User.objects.create_user(
            username="stranger@luanar", email="stranger@luanar", password="pass"
        )
        self.grant(grade_id=EMPLOYEE_TWO_GRADE_ID, days=5)

        self.assertIsNone(get_entitlement(stranger, self.sick, self.year))

    def test_blank_arguments_return_none(self):
        self.grant(days=7)

        self.assertIsNone(get_entitlement(None, self.sick, self.year))
        self.assertIsNone(get_entitlement(self.user, None, self.year))
        self.assertIsNone(get_entitlement(self.user, self.sick, None))
