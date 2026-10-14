"""Tests for the setup hub: apply-defaults, status, templates, and rollover.

The preset is the product's answer to a bare install having no roles, types,
bands, or year (migration 0028 removed the role seed), so these tests pin the
two properties the setup hub depends on: the whole spine is created in one
audited pass, and re-running it changes nothing HR has since edited.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import FinancialYear, GradeEntitlement, LeaveRule, LeaveType
from leave.services.setup import (
    ENTITLEMENT_BANDS,
    apply_defaults,
    rollover_financial_year,
    setup_status,
)
from org.models import ApproverRole

User = get_user_model()

STATUS_URL = "/api/v1/setup/status/"
TEMPLATES_URL = "/api/v1/setup/templates/"
APPLY_URL = "/api/v1/setup/apply-defaults/"
ROLLOVER_URL = "/api/v1/setup/rollover/"


class SetupServiceTests(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@setup.test",
            email="hr@setup.test",
            password="testpass123",
            role=User.Role.HR,
        )

    def test_apply_defaults_creates_the_whole_spine(self):
        result = apply_defaults(actor=self.hr)

        self.assertGreater(result.total_created, 0)
        self.assertEqual(FinancialYear.objects.count(), 1)
        self.assertEqual(GradeEntitlement.objects.count(), len(ENTITLEMENT_BANDS))
        self.assertEqual(LeaveType.objects.count(), 4)
        self.assertEqual(LeaveRule.objects.count(), 4)
        self.assertEqual(ApproverRole.objects.count(), 6)

    def test_apply_defaults_audits_per_object_and_summary(self):
        apply_defaults(actor=self.hr)

        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.PRESET_APPLIED
            ).exists()
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPROVER_ROLE,
                action=AuditEntry.Action.CREATED,
            ).exists()
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.LEAVE_TYPE,
                action=AuditEntry.Action.CREATED,
            ).exists()
        )

    def test_apply_defaults_is_idempotent(self):
        apply_defaults(actor=self.hr)
        counts = (
            FinancialYear.objects.count(),
            GradeEntitlement.objects.count(),
            LeaveType.objects.count(),
            LeaveRule.objects.count(),
            ApproverRole.objects.count(),
        )

        second = apply_defaults(actor=self.hr)

        self.assertEqual(second.total_created, 0)
        self.assertEqual(
            counts,
            (
                FinancialYear.objects.count(),
                GradeEntitlement.objects.count(),
                LeaveType.objects.count(),
                LeaveRule.objects.count(),
                ApproverRole.objects.count(),
            ),
        )
        # A no-op run writes no summary entry either.
        self.assertEqual(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.PRESET_APPLIED
            ).count(),
            1,
        )

    def test_apply_defaults_never_overwrites_existing_rows(self):
        apply_defaults(actor=self.hr)
        role = ApproverRole.objects.get(code="hod")
        role.label = "Edited Head of Department"
        role.save(update_fields=["label"])
        band = GradeEntitlement.objects.get(grade_start="A", grade_end="C")
        band.days = 99
        band.save(update_fields=["days"])

        apply_defaults(actor=self.hr)

        role.refresh_from_db()
        band.refresh_from_db()
        self.assertEqual(role.label, "Edited Head of Department")
        self.assertEqual(band.days, 99)

    def test_dry_run_writes_nothing(self):
        result = apply_defaults(actor=self.hr, dry_run=True)

        self.assertGreater(result.total_created, 0)
        self.assertTrue(result.dry_run)
        self.assertEqual(FinancialYear.objects.count(), 0)
        self.assertEqual(GradeEntitlement.objects.count(), 0)
        self.assertEqual(LeaveType.objects.count(), 0)
        self.assertEqual(LeaveRule.objects.count(), 0)
        self.assertEqual(ApproverRole.objects.count(), 0)

    def test_dry_run_previews_what_a_real_run_creates(self):
        preview = apply_defaults(actor=self.hr, dry_run=True)
        applied = apply_defaults(actor=self.hr)

        self.assertEqual(preview.created, applied.created)

    def test_setup_status_is_derived_from_live_data(self):
        before = setup_status()
        self.assertFalse(before["steps"]["financial_year"]["done"])
        self.assertFalse(before["complete"])

        apply_defaults(actor=self.hr)
        after = setup_status()

        self.assertTrue(after["steps"]["financial_year"]["done"])
        self.assertTrue(after["steps"]["leave_types"]["done"])
        self.assertTrue(after["steps"]["entitlements"]["done"])
        self.assertTrue(after["steps"]["roles"]["done"])
        # Still no team that can receive leave.
        self.assertFalse(after["steps"]["teams"]["done"])
        self.assertFalse(after["complete"])

    def test_rollover_opens_next_year_and_carries_rules(self):
        apply_defaults(actor=self.hr)

        result = rollover_financial_year(actor=self.hr)

        self.assertEqual(FinancialYear.objects.count(), 2)
        self.assertEqual(result.created["financial_year"], 1)
        self.assertEqual(result.created["leave_rules"], 4)
        # Bands are one row per grade range and persist across years.
        self.assertEqual(GradeEntitlement.objects.count(), len(ENTITLEMENT_BANDS))

    def test_rollover_activates_the_new_year_only(self):
        apply_defaults(actor=self.hr)

        rollover_financial_year(actor=self.hr)

        self.assertEqual(FinancialYear.objects.filter(is_active=True).count(), 1)
        active = FinancialYear.objects.get(is_active=True)
        old = FinancialYear.objects.order_by("start_date").first()
        self.assertGreater(active.start_date, old.start_date)

    def test_rollover_is_idempotent(self):
        apply_defaults(actor=self.hr)
        rollover_financial_year(actor=self.hr)

        second = rollover_financial_year(actor=self.hr)

        self.assertEqual(second.total_created, 0)
        self.assertEqual(FinancialYear.objects.count(), 2)
        self.assertEqual(LeaveRule.objects.count(), 8)


class SetupEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = User.objects.create_user(
            username="hr@setup-api.test",
            email="hr@setup-api.test",
            password="testpass123",
            role=User.Role.HR,
        )
        self.employee = User.objects.create_user(
            username="emp@setup-api.test",
            email="emp@setup-api.test",
            password="testpass123",
            role=User.Role.EMPLOYEE,
        )

    def test_requires_authentication(self):
        self.assertEqual(
            APIClient().get(STATUS_URL).status_code, 401
        )

    def test_non_hr_is_forbidden(self):
        self.client.force_authenticate(self.employee)
        self.assertEqual(self.client.get(STATUS_URL).status_code, 403)
        self.assertEqual(self.client.post(APPLY_URL, {}, format="json").status_code, 403)

    def test_status_endpoint(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(STATUS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertIn("steps", response.data)
        self.assertIn("complete", response.data)

    def test_templates_endpoint_lists_the_two_chains(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(TEMPLATES_URL)

        self.assertEqual(response.status_code, 200)
        keys = {template["key"] for template in response.data["templates"]}
        self.assertEqual(keys, {"academic", "administration"})
        academic = next(
            template
            for template in response.data["templates"]
            if template["key"] == "academic"
        )
        roles = [section["approver_role"] for section in academic["sections"]]
        self.assertEqual(roles, ["supervisor", "hod", "registrar", "dvc"])

    def test_apply_defaults_endpoint_previews_then_applies(self):
        self.client.force_authenticate(self.hr)

        preview = self.client.post(APPLY_URL, {"dry_run": True}, format="json")
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data["dry_run"])
        self.assertEqual(LeaveType.objects.count(), 0)

        applied = self.client.post(APPLY_URL, {}, format="json")
        self.assertEqual(applied.status_code, 200)
        self.assertGreater(applied.data["total_created"], 0)
        self.assertEqual(LeaveType.objects.count(), 4)

    def test_rollover_endpoint(self):
        self.client.force_authenticate(self.hr)
        self.client.post(APPLY_URL, {}, format="json")

        response = self.client.post(ROLLOVER_URL, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FinancialYear.objects.count(), 2)
