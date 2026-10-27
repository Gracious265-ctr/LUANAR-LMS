from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from audit.models import AuditEntry
from leave_types.models import LeaveType
from leave_types.serializers import LeaveTypeSerializer
from leave_types.services import (
    can_access_leave_config,
    check_notice,
    is_eligible,
    validate_notice,
)

User = get_user_model()


def make_user(role: str, username: str) -> User:
    return User.objects.create_user(
        username=username, password="pass", email=f"{username}@leave-config.test", role=role
    )


def employee(**dimensions):
    """Stand-in for the validation pipeline's ``EmployeeInfo``.

    Unspecified dimensions come back as ``None``, which is exactly how an
    unresolved employee arrives at :func:`is_eligible`.
    """
    return SimpleNamespace(
        branch=dimensions.get("branch"),
        grade=dimensions.get("grade"),
        gender=dimensions.get("gender"),
    )


class LeaveTypeCreateUpdateTest(APITestCase):
    """§6 "Core CRUD" — HR writes every rule field, exactly once."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr")
        self.employee = make_user(User.Role.EMPLOYEE, "emp")
        self.url = reverse("leave-config-type-list")

    def payload(self, **overrides):
        data = {
            "name": "Sabbatical Leave",
            "code": "SAB",
            "color": "purple",
            "description": "Long study leave.",
            "branch_scope": "academic",
            "eligible_grades": ["g", " e ", "", "G"],
            "eligible_gender": "any",
            "requires_supporting_document": True,
            "max_duration_days": 90,
            "notice_days": 30,
            "eligibility": "Academic staff only.",
            "eligibility_rules": [{"type": "min_service", "params": {"months": 3}}],
            "consumes_annual_entitlement": False,
            "plannable": True,
            "requires_institutional_registrar_approval": False,
        }
        data.update(overrides)
        return data

    def test_hr_can_create_leave_type_with_every_rule_field(self):
        self.client.force_authenticate(self.hr)
        res = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        created = LeaveType.objects.get(code="sab")
        self.assertEqual(created.name, "Sabbatical Leave")
        self.assertEqual(created.color, "purple")
        self.assertEqual(created.branch_scope, "academic")
        self.assertEqual(created.eligible_grades, ["G", "E"])
        self.assertEqual(created.eligible_grade_ids, ["G", "E"])
        self.assertEqual(created.eligible_gender, "any")
        self.assertTrue(created.requires_supporting_document)
        self.assertEqual(created.max_duration_days, 90)
        self.assertEqual(created.notice_days, 30)
        self.assertTrue(created.plannable)
        self.assertTrue(created.is_active)
        self.assertEqual(created.eligibility_rules[0]["type"], "min_service")

    def test_blank_code_is_derived_from_the_name(self):
        self.client.force_authenticate(self.hr)
        res = self.client.post(
            self.url, self.payload(name="Parental Leave", code=""), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(LeaveType.objects.get().code, "parental-leave")

    def test_create_is_audited(self):
        self.client.force_authenticate(self.hr)
        self.client.post(self.url, self.payload(), format="json")
        entry = AuditEntry.objects.get(action=AuditEntry.Action.CREATED)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.LEAVE_TYPE)
        self.assertEqual(entry.actor, self.hr)

    def test_create_refuses_to_reserve_the_annual_leave_name(self):
        """Annual leave is provisioned by an entitlement, never typed by hand."""
        self.client.force_authenticate(self.hr)
        res = self.client.post(
            self.url, self.payload(name="Annual Leave", code="yearly"), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", res.data)
        self.assertFalse(LeaveType.objects.filter(name="Annual Leave").exists())

    def test_create_refuses_to_reserve_the_annual_leave_code(self):
        self.client.force_authenticate(self.hr)
        res = self.client.post(
            self.url, self.payload(name="Yearly leave", code="annual-leave"), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", res.data)

    def test_patch_updates_rules_and_audits_the_change(self):
        leave_type = LeaveType.objects.create(name="Sabbatical Leave", notice_days=7)
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(url, {"notice_days": 14, "plannable": False}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        leave_type.refresh_from_db()
        self.assertEqual(leave_type.notice_days, 14)
        self.assertFalse(leave_type.plannable)

        entry = AuditEntry.objects.get(action=AuditEntry.Action.UPDATED)
        self.assertEqual(entry.detail["before"]["notice_days"], 7)
        self.assertEqual(entry.detail["after"]["notice_days"], 14)

    def test_patch_edits_the_provisioned_annual_types_rules(self):
        """Annual leave's rules are HR's to edit; only its identity is fixed.

        The Leave Rules screens that used to own these fields are retired, so
        this surface is the only place they can be changed.
        """
        leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", notice_days=7
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(
            url,
            {
                "notice_days": 14,
                "max_duration_days": 30,
                "requires_supporting_document": True,
                "plannable": False,
                "eligible_gender": "female",
                "requires_institutional_registrar_approval": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        leave_type.refresh_from_db()
        self.assertEqual(leave_type.notice_days, 14)
        self.assertEqual(leave_type.max_duration_days, 30)
        self.assertTrue(leave_type.requires_supporting_document)
        self.assertFalse(leave_type.plannable)
        self.assertEqual(leave_type.eligible_gender, "female")
        self.assertTrue(leave_type.requires_institutional_registrar_approval)
        self.assertTrue(
            AuditEntry.objects.filter(action=AuditEntry.Action.UPDATED).exists()
        )

    def test_patch_refuses_to_rename_the_provisioned_annual_type(self):
        """The row is found by name/code, so a rename would orphan entitlements."""
        leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", notice_days=7
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(url, {"name": "Yearly Leave"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn("name", res.data)

        leave_type.refresh_from_db()
        self.assertEqual(leave_type.name, "Annual Leave")
        self.assertEqual(leave_type.code, "annual")

    def test_patch_refuses_to_change_the_provisioned_annual_code(self):
        leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", notice_days=7
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(url, {"code": "yearly"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn("code", res.data)

    def test_patch_refuses_to_clear_the_annual_entitlement_marker(self):
        """The marker is what the balance ledger resolves to — not HR's to move."""
        leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", consumes_annual_entitlement=True
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(
            url, {"consumes_annual_entitlement": False}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

        leave_type.refresh_from_db()
        self.assertTrue(leave_type.consumes_annual_entitlement)

    def test_annual_rules_stay_editable_even_when_the_marker_is_resent(self):
        """Re-sending the marker unchanged is not an attempt to move it."""
        leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", consumes_annual_entitlement=True
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": leave_type.pk})
        res = self.client.patch(
            url,
            {"consumes_annual_entitlement": True, "notice_days": 3},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        leave_type.refresh_from_db()
        self.assertEqual(leave_type.notice_days, 3)

    def test_no_entitlement_field_exists_anywhere(self):
        """§1.3 — days per year is grade-based and lives elsewhere."""
        self.assertNotIn(
            "default_days_per_year",
            [field.name for field in LeaveType._meta.get_fields()],
        )
        self.assertNotIn("default_days_per_year", LeaveTypeSerializer.Meta.fields)
        self.assertNotIn(
            "default_days_per_year", set(LeaveTypeSerializer().get_fields())
        )


class LeaveTypeAccessTest(APITestCase):
    """§6 "Access" — reads for everyone, writes for HR only."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr")
        self.other = make_user(User.Role.APPROVER, "approver")
        self.active = LeaveType.objects.create(name="Annual Leave", is_active=True)
        self.retired = LeaveType.objects.create(name="Old Leave", is_active=False)
        self.list_url = reverse("leave-config-type-list")

    def test_non_hr_cannot_create(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(self.list_url, {"name": "Nope"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_hr_cannot_patch(self):
        self.client.force_authenticate(self.other)
        url = reverse("leave-config-type-detail", kwargs={"pk": self.active.pk})
        res = self.client.patch(url, {"notice_days": 99}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.active.refresh_from_db()
        self.assertNotEqual(self.active.notice_days, 99)

    def test_anonymous_cannot_list(self):
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_any_authenticated_user_can_read_the_active_list(self):
        self.client.force_authenticate(self.other)
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([row["name"] for row in res.data], ["Annual Leave"])

    def test_active_only_matches_the_default(self):
        self.client.force_authenticate(self.other)
        res = self.client.get(f"{self.list_url}?active_only=true")
        self.assertEqual(len(res.data), 1)

    def test_include_inactive_returns_every_type(self):
        self.client.force_authenticate(self.hr)
        res = self.client.get(f"{self.list_url}?include_inactive=true")
        self.assertEqual(
            sorted(row["name"] for row in res.data), ["Annual Leave", "Old Leave"]
        )

    def test_detail_of_a_retired_type_still_reads(self):
        self.client.force_authenticate(self.other)
        url = reverse("leave-config-type-detail", kwargs={"pk": self.retired.pk})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_delete_is_not_allowed(self):
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-detail", kwargs={"pk": self.active.pk})
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(LeaveType.objects.filter(pk=self.active.pk).exists())

    def test_can_access_leave_config_gates_by_role(self):
        self.assertTrue(can_access_leave_config(self.hr))
        self.assertFalse(can_access_leave_config(self.other))
        self.assertFalse(can_access_leave_config(None))


class LeaveTypeLifecycleTest(APITestCase):
    """§1.5 — deactivate and reactivate, never delete."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr")
        self.leave_type = LeaveType.objects.create(name="Sabbatical Leave", is_active=True)

    def post(self, action, user=None):
        self.client.force_authenticate(user or self.hr)
        url = reverse(f"leave-config-type-{action}", kwargs={"pk": self.leave_type.pk})
        return self.client.post(url)

    def test_deactivate_hides_the_type_but_keeps_the_row(self):
        res = self.post("deactivate")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.leave_type.refresh_from_db()
        self.assertFalse(self.leave_type.is_active)
        self.assertTrue(LeaveType.objects.filter(pk=self.leave_type.pk).exists())

        entry = AuditEntry.objects.get(action=AuditEntry.Action.DEACTIVATED)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.LEAVE_TYPE)
        self.assertEqual(entry.target_id, str(self.leave_type.pk))

    def test_reactivate_restores_the_type(self):
        self.leave_type.is_active = False
        self.leave_type.save(update_fields=["is_active"])
        res = self.post("reactivate")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.leave_type.refresh_from_db()
        self.assertTrue(self.leave_type.is_active)
        self.assertTrue(
            AuditEntry.objects.filter(action=AuditEntry.Action.ACTIVATED).exists()
        )

    def test_deactivating_twice_records_one_audit_entry(self):
        self.post("deactivate")
        self.post("deactivate")
        self.assertEqual(
            AuditEntry.objects.filter(action=AuditEntry.Action.DEACTIVATED).count(), 1
        )

    def test_non_hr_cannot_deactivate(self):
        other = make_user(User.Role.EMPLOYEE, "emp")
        res = self.post("deactivate", user=other)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.leave_type.refresh_from_db()
        self.assertTrue(self.leave_type.is_active)

    def test_deactivate_refuses_the_annual_type(self):
        """Retiring annual leave would empty every employee's leave selection."""
        annual = LeaveType.objects.create(name="Annual Leave", code="annual")
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-deactivate", kwargs={"pk": annual.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

        annual.refresh_from_db()
        self.assertTrue(annual.is_active)
        self.assertFalse(
            AuditEntry.objects.filter(action=AuditEntry.Action.DEACTIVATED).exists()
        )

    def test_reactivate_restores_a_retired_annual_type(self):
        """Restoring it is a repair, so it is deliberately not refused."""
        annual = LeaveType.objects.create(
            name="Annual Leave", code="annual", is_active=False
        )
        self.client.force_authenticate(self.hr)
        url = reverse("leave-config-type-reactivate", kwargs={"pk": annual.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        annual.refresh_from_db()
        self.assertTrue(annual.is_active)


class LeaveTypeValidationTest(APITestCase):
    """Inline validation per the Phase-2 form conventions (§3.3)."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr")
        self.client.force_authenticate(self.hr)
        self.url = reverse("leave-config-type-list")

    def post(self, **overrides):
        data = {"name": "Test Leave"}
        data.update(overrides)
        return self.client.post(self.url, data, format="json")

    def test_negative_notice_is_rejected(self):
        res = self.post(notice_days=-1)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("notice_days", res.data)

    def test_negative_max_duration_is_rejected(self):
        res = self.post(max_duration_days=0)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_duration_days", res.data)

    def test_unrestricted_dimensions_are_the_defaults(self):
        res = self.post()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        row = LeaveType.objects.get()
        self.assertEqual(row.branch_scope, "both")
        self.assertEqual(row.eligible_grades, [])
        self.assertEqual(row.eligible_gender, "any")
        self.assertEqual(row.color, "blue")

    def test_bad_colour_is_rejected(self):
        res = self.post(color="hotpink")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("color", res.data)

    def test_malformed_eligibility_rule_is_rejected(self):
        res = self.post(eligibility_rules=[{"params": {}}])
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("eligibility_rules", res.data)


class IsEligibleTest(APITestCase):
    """§6 "Rule correctness" — three independently optional dimensions."""

    def setUp(self):
        self.leave_type = LeaveType.objects.create(
            name="Maternity Leave",
            branch_scope="both",
            eligible_grades=["g", "e"],
            eligible_gender="female",
        )

    def test_unrestricted_dimensions_never_block(self):
        unrestricted = LeaveType.objects.create(
            name="Annual", branch_scope="both", eligible_grades=[], eligible_gender="any"
        )
        self.assertTrue(
            is_eligible(unrestricted, employee(branch="academic", grade="A", gender="male"))
        )
        self.assertTrue(
            is_eligible(unrestricted, employee(branch=None, grade=None, gender=None))
        )

    def test_branch_mismatch_fails(self):
        academic_only = LeaveType.objects.create(name="Sabbatical", branch_scope="academic")
        self.assertFalse(is_eligible(academic_only, employee(branch="administrative")))
        self.assertTrue(is_eligible(academic_only, employee(branch="academic")))

    def test_unresolvable_branch_fails_closed(self):
        academic_only = LeaveType.objects.create(name="Sabbatical", branch_scope="academic")
        self.assertFalse(is_eligible(academic_only, employee(branch=None)))

    def probe(self, **overrides):
        """Vary one dimension; resolve the other two as this type requires.

        ``is_eligible`` fails a *restricted* dimension closed when the employee
        carries no value for it, so a one-dimension probe has to hand the other
        two a passing value — otherwise the test would be asserting that an
        unresolved employee is eligible, which is the opposite of §1.4.
        """
        dims = dict(branch="academic", grade="g", gender="female")
        dims.update(overrides)
        return employee(**dims)

    def test_grade_allowance_is_case_insensitive_and_exact(self):
        self.assertTrue(is_eligible(self.leave_type, self.probe(grade="G")))
        self.assertTrue(is_eligible(self.leave_type, self.probe(grade=" e ")))
        self.assertFalse(is_eligible(self.leave_type, self.probe(grade="A")))
        # Restricted dimension, no value to check: blocked, not waved through.
        self.assertFalse(is_eligible(self.leave_type, self.probe(grade=None)))

    def test_gender_allowance(self):
        self.assertTrue(is_eligible(self.leave_type, self.probe(gender="female")))
        self.assertFalse(is_eligible(self.leave_type, self.probe(gender="male")))
        self.assertFalse(is_eligible(self.leave_type, self.probe(gender=None)))

    def test_all_three_must_pass(self):
        # Every dimension is restricted here, so each one can fail on its own.
        leave_type = LeaveType.objects.create(
            name="Sabbatical Leave",
            branch_scope="academic",
            eligible_grades=["g", "e"],
            eligible_gender="female",
        )
        self.assertTrue(is_eligible(leave_type, self.probe()))
        for dimension, wrong in (
            ("branch", "administrative"),
            ("grade", "a"),
            ("gender", "male"),
        ):
            with self.subTest(dimension=dimension):
                self.assertFalse(
                    is_eligible(leave_type, self.probe(**{dimension: wrong}))
                )


class NoticeTest(APITestCase):
    """§1.2 + §6 — one field, both consumers, ``None`` = no minimum."""

    def test_none_means_no_minimum(self):
        leave_type = LeaveType.objects.create(name="Sick", notice_days=None)
        self.assertTrue(validate_notice(leave_type, date(2026, 1, 5)))
        self.assertIsNone(check_notice(leave_type, date(2026, 1, 5), today=date(2026, 1, 5)))

    def test_calendar_notice(self):
        leave_type = LeaveType.objects.create(name="Study", notice_days=3)
        today = date(2026, 1, 5)

        too_soon = check_notice(leave_type, date(2026, 1, 6), today=today)
        self.assertIsNotNone(too_soon)
        self.assertEqual(too_soon.required, 3)
        self.assertEqual(too_soon.given, 1)
        self.assertEqual(too_soon.earliest_start, date(2026, 1, 8))
        self.assertEqual(too_soon.unit_label, "calendar days")

        self.assertIsNone(check_notice(leave_type, date(2026, 1, 8), today=today))
        self.assertFalse(validate_notice(leave_type, date(2026, 1, 6), today=today))
        self.assertTrue(validate_notice(leave_type, date(2026, 1, 8), today=today))

    def test_annual_notice_counts_working_days(self):
        leave_type = LeaveType.objects.create(name="Annual Leave", notice_days=2)
        monday = date(2026, 1, 5)

        # Tuesday gives one working day — one short of the two required.
        check = check_notice(leave_type, date(2026, 1, 6), today=monday)
        self.assertIsNotNone(check)
        self.assertEqual(check.given, 1)
        self.assertEqual(check.unit_label, "working days")
        self.assertEqual(check.earliest_start, date(2026, 1, 7))

        # A Saturday start skips the weekend entirely.
        self.assertIsNone(check_notice(leave_type, date(2026, 1, 10), today=monday))

    def test_holidays_extend_the_working_day_window(self):
        leave_type = LeaveType.objects.create(name="Annual Leave", notice_days=1)
        monday = date(2026, 1, 5)
        check = check_notice(
            leave_type, date(2026, 1, 6), today=monday, holidays={date(2026, 1, 6)}
        )
        self.assertIsNotNone(check)
        self.assertEqual(check.earliest_start, date(2026, 1, 7))
