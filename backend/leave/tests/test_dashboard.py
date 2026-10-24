"""Tests for ``GET /api/v1/leave/dashboard/`` (Unit 3).

The dashboard is scoped to the signed-in employee by construction, so the two
themes here are (a) it returns exactly the right sections in the right order and
(b) it never leaks another employee's leave. The annual balance reads the real
provider seam; the per-type rings read the provider-backed entitlement mapping
(``GradeLeaveEntitlement`` keyed by the fixture directory's external grade),
so both are exercised against real rows rather than a stub.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from leave.cancellations.models import LeaveBalanceTransaction
from leave.models import (
    FinancialYear,
    GradeEntitlement,
    GradeLeaveEntitlement,
    LeaveApplication,
)
from leave_types.models import LeaveType
from users.models import EmployeeProfile
from approvals.models import ApplicationStage, ApprovalDecision
from chains.testing import team_for

from .stubs import make_user

User = get_user_model()

TODAY = date(2026, 9, 21)
EFFECTIVE_FROM = date(2020, 1, 1)
FY_LABEL = "2026-27"

#: Fixture-directory emails so per-type rings resolve: the fixture provider
#: grades employee1/employee2 as "B" (directory/fixtures/seed_data.json).
OWNER_EMAIL = "employee1@test.luanar"
OTHER_EMAIL = "employee2@test.luanar"
FIXTURE_GRADE_ID = "B"


class DashboardTestBase(TestCase):
    url = "/api/v1/leave/dashboard/"

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user(OWNER_EMAIL)
        self.other = make_user(OTHER_EMAIL)
        self._profile(self.owner, grade="B")
        self._profile(self.other, grade="B")
        self.client.force_authenticate(user=self.owner)

        self.year = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

        # Annual leave, consumed from the shared annual balance. The rule the
        # type carries lives on the type itself since unit 06 folded the two.
        self.annual = LeaveType.objects.create(
            name="Annual Leave",
            code="annual",
            max_duration_days=30,
            consumes_annual_entitlement=True,
        )
        GradeEntitlement.objects.create(
            leave_type=self.annual,
            grade_start="A",
            grade_end="Z",
            days=21,
            effective_from=EFFECTIVE_FROM,
        )

        # A separately-granted type, so per-type rings have something to show.
        # Per-type entitlements are keyed by the provider's external grade id.
        self.sick = LeaveType.objects.create(name="Sick Leave", code="sick")
        GradeLeaveEntitlement.objects.create(
            grade_id=FIXTURE_GRADE_ID,
            leave_type=self.sick,
            financial_year=self.year,
            days=10,
        )

    def _profile(self, user, *, grade):
        return EmployeeProfile.objects.create(
            user=user,
            team=team_for("Administration Team"),
            designation="Administrative Officer",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade=grade,
            appointment_date=date(2022, 3, 15),
            gender=EmployeeProfile.Gender.FEMALE,
        )

    def application(
        self,
        status_=LeaveApplication.Status.SUBMITTED,
        *,
        user=None,
        leave_type=None,
        days=3,
        start=date(2026, 11, 3),
        fy_label=FY_LABEL,
    ):
        return LeaveApplication.objects.create(
            employee=user or self.owner,
            status=status_,
            leave_type_id=leave_type.pk if leave_type else None,
            start_date=start,
            end_date=start,
            calculated_days=days,
            financial_year_label=fy_label,
        )

    def get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data


class DashboardAuthTests(DashboardTestBase):
    def test_requires_authentication(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_has_every_section(self):
        payload = self.get()
        for key in (
            "balances",
            "pending_count",
            "upcoming_leave",
            "needs_attention",
            "drafts",
            "recent",
        ):
            with self.subTest(key=key):
                self.assertIn(key, payload)


class DashboardStatCardTests(DashboardTestBase):
    """The two stat cards: pending applications and the next upcoming leave."""

    def test_pending_count_counts_only_submitted(self):
        self.application(LeaveApplication.Status.SUBMITTED)
        self.application(LeaveApplication.Status.SUBMITTED)
        for other in (
            LeaveApplication.Status.DRAFT,
            LeaveApplication.Status.APPROVED,
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.CORRECTION_REQUIRED,
            LeaveApplication.Status.CANCELLED,
        ):
            self.application(other)

        self.assertEqual(self.get()["pending_count"], 2)

    def test_pending_count_is_scoped_to_the_employee(self):
        self.application(LeaveApplication.Status.SUBMITTED)
        self.application(LeaveApplication.Status.SUBMITTED, user=self.other)

        self.assertEqual(self.get()["pending_count"], 1)

    def test_upcoming_is_null_without_a_future_approved_leave(self):
        past = timezone.localdate() - timedelta(days=5)
        self.application(LeaveApplication.Status.APPROVED, start=past)
        self.application(
            LeaveApplication.Status.SUBMITTED,
            start=timezone.localdate() + timedelta(days=2),
        )

        self.assertIsNone(self.get()["upcoming_leave"])

    def test_upcoming_is_the_earliest_approved_future_leave(self):
        today = timezone.localdate()
        later = self.application(
            LeaveApplication.Status.APPROVED, start=today + timedelta(days=10)
        )
        sooner = self.application(
            LeaveApplication.Status.APPROVED, start=today + timedelta(days=3)
        )

        upcoming = self.get()["upcoming_leave"]
        self.assertEqual(upcoming["id"], str(sooner.id))
        self.assertNotEqual(upcoming["id"], str(later.id))
        self.assertEqual(upcoming["days_until"], 3)
        self.assertEqual(upcoming["start_date"], sooner.start_date)

    def test_upcoming_includes_leave_starting_today(self):
        self.application(
            LeaveApplication.Status.APPROVED, start=timezone.localdate()
        )

        upcoming = self.get()["upcoming_leave"]
        self.assertIsNotNone(upcoming)
        self.assertEqual(upcoming["days_until"], 0)

    def test_upcoming_resolves_the_leave_type_name(self):
        self.application(
            LeaveApplication.Status.APPROVED,
            leave_type=self.annual,
            start=timezone.localdate() + timedelta(days=4),
        )

        self.assertEqual(self.get()["upcoming_leave"]["leave_type"], "Annual Leave")


class DashboardScopingTests(DashboardTestBase):
    def test_another_employees_applications_never_appear(self):
        self.application(LeaveApplication.Status.REJECTED, user=self.other)
        self.application(LeaveApplication.Status.DRAFT, user=self.other)
        self.application(LeaveApplication.Status.APPROVED, user=self.other)

        payload = self.get()
        self.assertEqual(payload["needs_attention"], [])
        self.assertEqual(payload["drafts"], [])
        self.assertEqual(payload["recent"], [])

    def test_each_employee_sees_only_their_own(self):
        self.application(LeaveApplication.Status.CORRECTION_REQUIRED)
        self.application(LeaveApplication.Status.CORRECTION_REQUIRED, user=self.other)

        owner_payload = self.get()
        self.client.force_authenticate(user=self.other)
        other_payload = self.get()

        self.assertEqual(len(owner_payload["needs_attention"]), 1)
        self.assertEqual(len(other_payload["needs_attention"]), 1)
        self.assertNotEqual(
            owner_payload["needs_attention"][0]["id"],
            other_payload["needs_attention"][0]["id"],
        )


class DashboardSectionTests(DashboardTestBase):
    def test_needs_attention_covers_rejected_and_correction_required(self):
        rejected = self.application(LeaveApplication.Status.REJECTED)
        correction = self.application(LeaveApplication.Status.CORRECTION_REQUIRED)
        self.application(LeaveApplication.Status.APPROVED)  # excluded

        ids = {item["id"] for item in self.get()["needs_attention"]}
        self.assertEqual(ids, {str(rejected.id), str(correction.id)})

    def test_needs_attention_is_most_recently_updated_first(self):
        old = self.application(LeaveApplication.Status.REJECTED)
        new = self.application(LeaveApplication.Status.CORRECTION_REQUIRED)
        LeaveApplication.objects.filter(pk=old.pk).update(
            updated_at="2026-01-01T00:00:00Z"
        )
        LeaveApplication.objects.filter(pk=new.pk).update(
            updated_at="2026-06-01T00:00:00Z"
        )
        ids = [item["id"] for item in self.get()["needs_attention"]]
        self.assertEqual(ids, [str(new.id), str(old.id)])

    def test_needs_attention_is_capped_at_five(self):
        for _ in range(6):
            self.application(LeaveApplication.Status.REJECTED)
        self.assertEqual(len(self.get()["needs_attention"]), 5)

    def test_drafts_only_contains_drafts(self):
        draft = self.application(LeaveApplication.Status.DRAFT)
        self.application(LeaveApplication.Status.SUBMITTED)
        ids = [item["id"] for item in self.get()["drafts"]]
        self.assertEqual(ids, [str(draft.id)])

    def test_drafts_are_capped_at_five(self):
        for _ in range(6):
            self.application(LeaveApplication.Status.DRAFT)
        self.assertEqual(len(self.get()["drafts"]), 5)

    def test_recent_excludes_drafts_and_is_creation_ordered(self):
        draft = self.application(LeaveApplication.Status.DRAFT)
        first = self.application(LeaveApplication.Status.SUBMITTED)
        second = self.application(LeaveApplication.Status.APPROVED)
        LeaveApplication.objects.filter(pk=first.pk).update(
            created_at="2026-01-01T00:00:00Z"
        )
        LeaveApplication.objects.filter(pk=second.pk).update(
            created_at="2026-02-01T00:00:00Z"
        )

        ids = [item["id"] for item in self.get()["recent"]]
        self.assertEqual(ids, [str(second.id), str(first.id)])
        self.assertNotIn(str(draft.id), ids)

    def test_recent_is_capped_at_five(self):
        for _ in range(6):
            self.application(LeaveApplication.Status.APPROVED)
        self.assertEqual(len(self.get()["recent"]), 5)


class DashboardSerializationTests(DashboardTestBase):
    def test_submitted_is_presented_as_pending(self):
        self.application(LeaveApplication.Status.SUBMITTED)
        self.assertEqual(self.get()["recent"][0]["status"], "pending")

    def test_leave_type_name_is_resolved_from_the_soft_id(self):
        self.application(LeaveApplication.Status.APPROVED, leave_type=self.annual)
        self.assertEqual(self.get()["recent"][0]["leave_type"], "Annual Leave")

    def test_leave_type_is_null_when_unset(self):
        self.application(LeaveApplication.Status.APPROVED)
        self.assertIsNone(self.get()["recent"][0]["leave_type"])

    def test_excerpt_is_the_latest_decision_comment(self):
        app = self.application(LeaveApplication.Status.CORRECTION_REQUIRED)
        self._decision(app, "The first note.", decided_at="2026-01-01T00:00:00Z")
        self._decision(
            app, "Please attach the medical certificate.", decided_at="2026-02-01T00:00:00Z"
        )

        excerpt = self.get()["needs_attention"][0]["last_comment_excerpt"]
        self.assertEqual(excerpt, "Please attach the medical certificate.")

    def test_excerpt_is_truncated_to_sixty_characters(self):
        app = self.application(LeaveApplication.Status.REJECTED)
        self._decision(app, "x" * 100)
        excerpt = self.get()["needs_attention"][0]["last_comment_excerpt"]
        self.assertEqual(len(excerpt), 60)
        self.assertTrue(excerpt.endswith("…"))

    def test_excerpt_is_null_without_a_comment(self):
        self.application(LeaveApplication.Status.REJECTED)
        self.assertIsNone(self.get()["needs_attention"][0]["last_comment_excerpt"])

    def _decision(self, application, comment, *, cycle=1, decided_at=None):
        order = (
            ApplicationStage.objects.filter(
                application=application, submission_cycle=cycle
            ).count()
            + 1
        )
        stage = ApplicationStage.objects.create(
            application=application,
            stage_order=order,
            role="hod",
            role_label="Head of Department",
            status=ApplicationStage.Status.WAITING,
            submission_cycle=cycle,
        )
        return ApprovalDecision.objects.create(
            application=application,
            stage=stage,
            approver=self.other,
            approver_name="Other Person",
            role_label="Head of Department",
            action=ApprovalDecision.Action.RETURN_FOR_CORRECTION,
            comment=comment,
            submission_cycle=cycle,
            **({"decided_at": decided_at} if decided_at else {}),
        )


class DashboardBalanceTests(DashboardTestBase):
    def test_annual_ring_leads_with_entitlement_and_used(self):
        # A nine-day deduction leaves 12 of the 21-day entitlement available.
        app = self.application(LeaveApplication.Status.APPROVED, days=9)
        LeaveBalanceTransaction.objects.create(
            employee=self.owner,
            financial_year=FY_LABEL,
            leave_type=self.annual.pk,
            application=app,
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal("9.0"),
        )

        annual = self.get()["balances"][0]
        self.assertEqual(annual, {"leave_type": "Annual Leave", "used": 9, "total": 21})

    def test_annual_ring_reports_no_usage_without_a_ledger_entry(self):
        annual = self.get()["balances"][0]
        self.assertEqual(annual["used"], 0)
        self.assertEqual(annual["total"], 21)

    def test_per_type_ring_sums_approved_days_of_that_type(self):
        self.application(LeaveApplication.Status.APPROVED, leave_type=self.sick, days=2)
        self.application(LeaveApplication.Status.APPROVED, leave_type=self.sick, days=3)
        # Pending and another year do not count.
        self.application(LeaveApplication.Status.SUBMITTED, leave_type=self.sick, days=4)
        self.application(
            LeaveApplication.Status.APPROVED,
            leave_type=self.sick,
            days=5,
            fy_label="2025-26",
        )

        sick = next(
            ring for ring in self.get()["balances"] if ring["leave_type"] == "Sick Leave"
        )
        self.assertEqual(sick, {"leave_type": "Sick Leave", "used": 5, "total": 10})

    def test_annual_type_is_not_duplicated_as_a_per_type_ring(self):
        labels = [ring["leave_type"] for ring in self.get()["balances"]]
        self.assertEqual(labels.count("Annual Leave"), 1)

    def test_balances_are_empty_without_a_grade(self):
        no_grade = make_user("dashboard-no-grade@luanar")
        EmployeeProfile.objects.create(
            user=no_grade,
            team=team_for("Administration Team"),
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="",
            appointment_date=date(2022, 3, 15),
        )
        self.client.force_authenticate(user=no_grade)
        self.assertEqual(self.get()["balances"], [])

    def test_balances_are_capped_at_four(self):
        for index in range(4):
            extra = LeaveType.objects.create(
                name=f"Extra {index}", code=f"extra-{index}"
            )
            GradeLeaveEntitlement.objects.create(
                grade_id=FIXTURE_GRADE_ID,
                leave_type=extra,
                financial_year=self.year,
                days=5 + index,
            )
        self.assertEqual(len(self.get()["balances"]), 4)

    def test_unconfigured_type_is_omitted_rather_than_zero(self):
        LeaveType.objects.create(name="Compassionate Leave", code="compassionate")

        labels = [ring["leave_type"] for ring in self.get()["balances"]]
        self.assertNotIn("Compassionate Leave", labels)

    def test_no_provider_record_means_no_typed_rings(self):
        # A local profile grade and a typed band are not enough any more: the
        # per-type rings need a provider record (matched by email) to know the
        # employee's external grade. The annual ring is unaffected.
        orphan = make_user("dashboard-owner@luanar")
        self._profile(orphan, grade="B")
        GradeEntitlement.objects.create(
            leave_type=self.sick,
            grade_start="A",
            grade_end="Z",
            days=10,
            effective_from=EFFECTIVE_FROM,
        )
        self.client.force_authenticate(user=orphan)

        labels = [ring["leave_type"] for ring in self.get()["balances"]]
        self.assertEqual(labels, ["Annual Leave"])
