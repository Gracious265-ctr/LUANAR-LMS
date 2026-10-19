"""Leave entitlement, leave-type, rule, and holiday coverage.

The department suite that used to live alongside this — ``Department`` itself, its
HR-only CRUD, and the ``Department`` assertion in the bootstrap test below — was
removed with the model. A fresh database is now checked for the entities that do
exist instead.
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import EmployeeProfile, User

from audit.models import AuditEntry
from workflows.models import (
    Section,
    SectionMember,
    Workflow,
)
from organisation.models import (
    ApproverRole,
    Campus,
    RoleAssignment,
)
from teams.models import (
    Team,
)

from ..admin import (
    FinancialYearAdmin,
    FinancialYearAdminForm,
    GradeEntitlementAdmin,
    GradeEntitlementAdminForm,
    PublicHolidayAdmin,
    PublicHolidayAdminForm,
)
from leave_config.models import LeaveType

from ..models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    PublicHoliday,
    SupportingDocument,
)
from ..services import (
    active_financial_year,
    financial_year_for_date,
    find_annual_leave_type,
    public_holidays_between,
    resolve_grade_entitlement,
)
from ..services.working_days import calculate_working_days
from ..services.storage import upload_document
from ..serializers import SupportingDocumentSerializer

SEED_PASSWORD = "testpass123"
TODAY = timezone.localdate()


class EntitlementResolutionTests(TestCase):
    """Service-level grade/entitlement resolution behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.ac = GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=21, effective_from=TODAY
        )
        cls.dg = GradeEntitlement.objects.create(
            grade_start="D", grade_end="G", days=24, effective_from=TODAY
        )
        cls.hu = GradeEntitlement.objects.create(
            grade_start="H", grade_end="U", days=30, effective_from=TODAY
        )

    def test_default_bands_resolve_correctly(self):
        expectations = {
            "A": 21,
            "C": 21,
            "D": 24,
            "G": 24,
            "H": 30,
            "U": 30,
        }
        for grade, expected in expectations.items():
            with self.subTest(grade=grade):
                self.assertEqual(
                    resolve_grade_entitlement(grade).days, expected
                )

    def test_matching_is_case_insensitive(self):
        self.assertEqual(resolve_grade_entitlement("b").days, 21)
        self.assertEqual(resolve_grade_entitlement("G").days, 24)

    def test_unmapped_grade_returns_none(self):
        self.assertIsNone(resolve_grade_entitlement("V"))
        self.assertIsNone(resolve_grade_entitlement("Z"))

    def test_blank_grade_returns_none(self):
        self.assertIsNone(resolve_grade_entitlement(""))
        self.assertIsNone(resolve_grade_entitlement("   "))
        self.assertIsNone(resolve_grade_entitlement(None))

    def test_resolution_prefers_latest_effective_rule_when_overlapping(self):
        # Overlapping rules are rejected at the serializer/admin layers, so this
        # only guards resolution determinism for any pre-existing rows.
        future = TODAY + timedelta(days=365)
        GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=22, effective_from=future
        )

        self.assertEqual(resolve_grade_entitlement("B", TODAY).days, 21)
        self.assertEqual(
            resolve_grade_entitlement("B", future - timedelta(days=1)).days, 21
        )
        self.assertEqual(resolve_grade_entitlement("B", future).days, 22)
        self.assertEqual(
            resolve_grade_entitlement("B", future + timedelta(days=1)).days, 22
        )

    def test_boundary_effective_from_applies_from_its_date(self):
        self.assertEqual(resolve_grade_entitlement("A", TODAY).days, 21)


class GradeEntitlementEndpointTests(TestCase):
    """HR-only CRUD and resolution for entitlement rules."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )

        self.effective = TODAY - timedelta(days=5)
        self.ac = GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=21, effective_from=self.effective
        )
        self.dg = GradeEntitlement.objects.create(
            grade_start="D", grade_end="G", days=24, effective_from=self.effective
        )
        GradeEntitlement.objects.create(
            grade_start="H", grade_end="U", days=30, effective_from=self.effective
        )

        self.list_url = "/api/v1/entitlements/"
        self.detail_url = f"/api/v1/entitlements/{self.ac.id}/"
        self.resolve_url = "/api/v1/entitlements/resolve/"

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_and_update_require_authentication(self):
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_resolve_requires_authentication(self):
        response = self.client.get(self.resolve_url, {"grade": "B"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.post(self.list_url, {}).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.get(self.resolve_url, {"grade": "B"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_can_list_entitlements(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)  # type: ignore[index]
        first = response.data["results"][0]  # type: ignore[index]
        self.assertEqual(first["grade_start"], "A")
        self.assertEqual(first["grade_end"], "C")
        self.assertEqual(first["days"], 21)

    def test_hr_can_retrieve_entitlement(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 21)  # type: ignore[index]

    def test_create_normalizes_grades_and_returns_201(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": " v ",
                "grade_end": "z",
                "days": 12,
                "effective_from": TODAY.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["grade_start"], "V")  # type: ignore[index]
        self.assertEqual(response.data["grade_end"], "Z")  # type: ignore[index]

    def test_create_requires_fields(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"grade_start": "A", "days": 10, "effective_from": TODAY.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.list_url,
            {"grade_start": "A", "grade_end": "C", "days": 10},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_inverted_range(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "Z",
                "grade_end": "A",
                "days": 10,
                "effective_from": TODAY.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_zero_days(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "A",
                "grade_end": "C",
                "days": 0,
                "effective_from": TODAY.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_same_date_overlap(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "B",
                "grade_end": "C",
                "days": 25,
                "effective_from": self.effective.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grade_start", response.data)  # type: ignore[index]

    def test_create_rejects_overlap_on_any_effective_date(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "A",
                "grade_end": "C",
                "days": 22,
                "effective_from": (TODAY + timedelta(days=365)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grade_start", response.data)  # type: ignore[index]

    def test_create_allows_non_overlapping_range_on_an_earlier_date(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "V",
                "grade_end": "Z",
                "days": 10,
                "effective_from": (self.effective - timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_hr_can_patch_entitlement(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"days": 23})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ac.refresh_from_db()
        self.assertEqual(self.ac.days, 23)

    def test_patch_rejects_overlap_with_another_rule(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"grade_end": "G"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grade_start", response.data)  # type: ignore[index]

    def test_delete_not_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_resolve_returns_effective_entitlement(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.resolve_url, {"grade": "B"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["grade"], "B")  # type: ignore[index]
        self.assertEqual(response.data["days"], 21)  # type: ignore[index]
        self.assertEqual(response.data["effective_from"], self.effective.isoformat())  # type: ignore[index]

    def test_resolve_is_case_insensitive_and_normalizes_grade(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.resolve_url, {"grade": "h"})
        self.assertEqual(response.data["grade"], "H")  # type: ignore[index]
        self.assertEqual(response.data["days"], 30)  # type: ignore[index]

    def test_resolve_unmapped_grade_returns_null_days(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.resolve_url, {"grade": "V"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["days"])  # type: ignore[index]
        self.assertIsNone(response.data["effective_from"])  # type: ignore[index]

    def test_resolve_respects_as_of(self):
        self.client.force_authenticate(user=self.hr_user)
        before = (self.effective - timedelta(days=1)).isoformat()
        response = self.client.get(self.resolve_url, {"grade": "B", "as_of": before})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["days"])  # type: ignore[index]

    def test_resolve_requires_grade(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.resolve_url, {"grade": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resolve_rejects_invalid_as_of(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.resolve_url, {"grade": "B", "as_of": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_provisions_annual_leave_and_its_rule(self):
        """Saving an entitlement is what brings annual leave into existence.

        The type arrives with the rule already on it (unit 06 folded the two):
        without it the employee catalog has nothing to offer and the catalog's
        duration stays empty.
        """
        maternity = LeaveType.objects.create(name="Maternity leave", code="maternity")
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "V",
                "grade_end": "W",
                "days": 30,
                "effective_from": TODAY.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        annual = find_annual_leave_type()
        self.assertIsNotNone(annual)
        self.assertEqual(response.data["leave_type"], annual.pk)  # type: ignore[index]
        self.assertEqual(response.data["leave_type_name"], "Annual Leave")  # type: ignore[index]
        # The band that was just written grants annual leave, not maternity.
        self.assertEqual(GradeEntitlement.objects.get(pk=response.data["id"]).leave_type, annual)  # type: ignore[index]

        # The rule rides on the type itself and is visible in the Leave
        # Configuration registry rather than a separate rules table.
        self.assertTrue(annual.consumes_annual_entitlement)
        self.assertEqual(annual.max_duration_days, 30)

        types = self.client.get("/api/v1/leave-config/types/")
        self.assertEqual(types.status_code, status.HTTP_200_OK)
        listed = {item["id"]: item for item in types.data}  # type: ignore[union-attr]
        self.assertIn(annual.pk, listed)
        self.assertEqual(listed[annual.pk]["max_duration_days"], 30)
        self.assertTrue(listed[annual.pk]["consumes_annual_entitlement"])
        # Maternity is a type HR made, so it is listed — but provisioning this
        # band grants annual leave only, and hands it no policy.
        self.assertIn(maternity.pk, listed)
        self.assertIsNone(listed[maternity.pk]["max_duration_days"])
        self.assertFalse(listed[maternity.pk]["consumes_annual_entitlement"])

    def test_create_provisions_annual_leave_when_a_type_is_supplied(self):
        """``leave_type`` is read-only, so a supplied one cannot skip provisioning."""
        self.client.force_authenticate(user=self.hr_user)
        maternity = LeaveType.objects.create(name="Maternity leave", code="maternity")
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "V",
                "grade_end": "W",
                "days": 30,
                "effective_from": TODAY.isoformat(),
                "leave_type": maternity.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        band = GradeEntitlement.objects.get(pk=response.data["id"])  # type: ignore[index]
        self.assertEqual(band.leave_type, find_annual_leave_type())
        self.assertTrue(band.leave_type.consumes_annual_entitlement)
        self.assertEqual(band.leave_type.max_duration_days, 30)

    def test_second_band_reuses_the_same_annual_type(self):
        """Provisioning is idempotent: one type, one policy."""
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(
            self.list_url,
            {
                "grade_start": "V",
                "grade_end": "W",
                "days": 30,
                "effective_from": TODAY.isoformat(),
            },
        )
        response = self.client.post(
            self.list_url,
            {
                "grade_start": "X",
                "grade_end": "Z",
                "days": 21,
                "effective_from": TODAY.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            LeaveType.objects.filter(code__in=["annual", "annual-leave"]).count(), 1
        )

    def test_provisioned_leave_type_is_audited(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(
            self.list_url,
            {
                "grade_start": "V",
                "grade_end": "W",
                "days": 30,
                "effective_from": TODAY.isoformat(),
            },
        )
        annual = find_annual_leave_type()
        entries = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.LEAVE_TYPE, target_id=str(annual.pk)
        )
        # One action, one entry: the type is created carrying its policy, so
        # there is no follow-up "applied the rule" row and no separate rule
        # target to audit.
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().actor, self.hr_user)
        self.assertEqual(entries.first().action, AuditEntry.Action.CREATED)
        self.assertEqual(annual.max_duration_days, 30)


class CleanDatabaseBootstrapTests(TestCase):
    """The product must run from an empty database.

    A superadmin creates HR, and HR creates campuses, teams, workflows,
    entitlements, and leave types through the frontend. Nothing may supply those
    rows behind the UI's back — a seeder or a data migration that quietly created
    them would leave HR looking at configuration it did not create and could not
    explain. A test database is built by the migrations alone, which makes it
    exactly that starting point.

    Approver roles are HR data too: a fresh install has **none**. Migration
    0011 used to seed six canonical codes for the old hardcoded stages; 0028
    removes them again when nothing references them, so migrate-from-zero ends
    at zero roles. HR creates the roles the institution actually uses through
    the Roles screen.
    """

    def test_a_fresh_database_has_no_accounts(self):
        self.assertFalse(User.objects.exists())
        self.assertFalse(EmployeeProfile.objects.exists())

    def test_a_fresh_database_has_no_approver_roles(self):
        self.assertFalse(ApproverRole.objects.exists())

    def test_a_fresh_database_has_no_business_data(self):
        self.assertFalse(Campus.objects.exists())
        self.assertFalse(Team.objects.exists())
        self.assertFalse(Workflow.objects.exists())
        self.assertFalse(Section.objects.exists())
        self.assertFalse(SectionMember.objects.exists())
        self.assertFalse(RoleAssignment.objects.exists())
        self.assertFalse(GradeEntitlement.objects.exists())
        self.assertFalse(LeaveType.objects.exists())

    def test_the_first_hr_account_arrives_through_the_admin_users_endpoint(self):
        """The bootstrap door is the API, and it hands over no configuration.

        Creating HR is the first write a deployment makes, so it is the moment a
        stray seed row would first become visible. The account arrives alone:
        nothing about approving leave comes with it.
        """
        superuser = User.objects.create_superuser(
            username="root@test.luanar",
            email="root@test.luanar",
            password=SEED_PASSWORD,
        )
        client = APIClient()
        client.force_authenticate(user=superuser)
        response = client.post(
            "/api/v1/admin-users/",
            {
                "first_name": "Ada",
                "last_name": "Person",
                "email": "ada@test.luanar",
                "password": "longenough",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="ada@test.luanar").role, User.Role.HR)
        self.assertFalse(Campus.objects.exists())
        self.assertFalse(Team.objects.exists())
        self.assertFalse(Workflow.objects.exists())
        self.assertFalse(RoleAssignment.objects.exists())
        self.assertFalse(GradeEntitlement.objects.exists())
        self.assertFalse(LeaveType.objects.exists())


class GradeEntitlementAdminTests(TestCase):
    """Admin form applies the overlap rule and the rule is not deletable."""

    def setUp(self):
        self.ac = GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=21, effective_from=TODAY
        )

    def _data(self, **overrides):
        data = {
            "grade_start": "A",
            "grade_end": "C",
            "days": 21,
            "effective_from": TODAY.isoformat(),
        }
        data.update(overrides)
        return data

    def test_form_rejects_overlapping_range(self):
        form = GradeEntitlementAdminForm(
            data=self._data(grade_start="B", grade_end="D")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("grade_start", form.errors)

    def test_form_allows_editing_the_same_rule(self):
        form = GradeEntitlementAdminForm(
            data=self._data(days=22), instance=self.ac
        )
        self.assertTrue(form.is_valid())

    def test_form_allows_non_overlapping_range(self):
        form = GradeEntitlementAdminForm(
            data=self._data(grade_start="V", grade_end="Z")
        )
        self.assertTrue(form.is_valid())

    def test_admin_does_not_allow_delete(self):
        model_admin = GradeEntitlementAdmin(GradeEntitlement, AdminSite())
        self.assertFalse(model_admin.has_delete_permission(request=None))

    def test_form_leave_type_is_not_editable(self):
        """An entitlement is an annual-leave entitlement, so the type is settled."""
        form = GradeEntitlementAdminForm(data=self._data(), instance=self.ac)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.fields["leave_type"].required)
        self.assertTrue(form.fields["leave_type"].disabled)

    def test_admin_save_provisions_annual_leave(self):
        hr_user = User.objects.create_user(
            username="hr@admin.test",
            email="hr@admin.test",
            password=SEED_PASSWORD,
            role=User.Role.HR,
        )
        model_admin = GradeEntitlementAdmin(GradeEntitlement, AdminSite())
        band = GradeEntitlement(
            grade_start="X", grade_end="Z", days=21, effective_from=TODAY
        )
        request = mock.Mock(user=hr_user)
        form = GradeEntitlementAdminForm(
            data={
                "grade_start": "X",
                "grade_end": "Z",
                "days": 21,
                "effective_from": TODAY.isoformat(),
            },
            instance=band,
        )
        self.assertTrue(form.is_valid(), form.errors)
        model_admin.save_model(request, band, form, change=False)
        annual = find_annual_leave_type()
        self.assertEqual(band.leave_type, annual)
        self.assertTrue(annual.consumes_annual_entitlement)
        self.assertEqual(annual.max_duration_days, 21)


class EmployeeLeaveTypeOptionsTests(TestCase):
    """Read-only employee-facing leave-type catalog with live rule policy."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.employee_user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )
        self.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )

        EmployeeProfile.objects.create(user=self.employee_user, grade="B")
        EmployeeProfile.objects.create(user=self.hr_user, grade="B")

        self.annual = LeaveType.objects.create(
            name="Annual leave",
            code="annual",
            max_duration_days=99,
            requires_supporting_document=False,
        )
        self.paternity = LeaveType.objects.create(
            name="Paternity leave",
            code="paternity",
            max_duration_days=10,
            requires_supporting_document=True,
        )

        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=10,
            effective_from=TODAY - timedelta(days=1),
            leave_type=self.paternity,
        )
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=TODAY - timedelta(days=1),
            leave_type=self.annual,
        )

        self.url = "/api/v1/employee/leave-types/"

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employee_can_list_options_unpaginated(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)  # type: ignore[arg-type]
        by_code = {item["code"]: item for item in response.data}  # type: ignore[union-attr]

        paternity = by_code["paternity"]
        self.assertEqual(paternity["max_duration_days"], 10)
        self.assertTrue(paternity["requires_supporting_document"])

    def test_rules_are_read_straight_off_the_type(self):
        # Unit 06 collapsed the effective-dated rule into the type, so what HR
        # configured is exactly what the employee catalog shows.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_code = {item["code"]: item for item in response.data}  # type: ignore[union-attr]

        annual = by_code["annual"]
        self.assertEqual(annual["max_duration_days"], 99)
        self.assertFalse(annual["requires_supporting_document"])

    def test_hr_can_read_the_same_catalog(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FinancialYearResolutionTests(TestCase):
    """Service-level financial-year and holiday resolution behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.fy_current = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )
        cls.fy_future = FinancialYear.objects.create(
            start_date=date(2027, 7, 1),
            end_date=date(2028, 6, 30),
        )
        PublicHoliday.objects.create(
            name="Independence Day", date=date(2026, 7, 6)
        )
        PublicHoliday.objects.create(
            name="Christmas Day", date=date(2026, 12, 25)
        )

    def test_financial_year_for_date_matches_containing_period(self):
        self.assertEqual(
            financial_year_for_date(date(2026, 9, 17)), self.fy_current
        )

    def test_financial_year_for_date_matches_future_period(self):
        self.assertEqual(
            financial_year_for_date(date(2027, 9, 17)), self.fy_future
        )

    def test_financial_year_for_date_none_outside_periods(self):
        self.assertIsNone(financial_year_for_date(date(2025, 1, 1)))
        self.assertIsNone(financial_year_for_date(date(2028, 8, 1)))

    def test_bounds_are_inclusive(self):
        self.assertEqual(
            financial_year_for_date(date(2026, 7, 1)), self.fy_current
        )
        self.assertEqual(
            financial_year_for_date(date(2027, 6, 30)), self.fy_current
        )
        self.assertEqual(
            financial_year_for_date(date(2027, 7, 1)), self.fy_future
        )

    def test_active_financial_year(self):
        self.assertEqual(active_financial_year(), self.fy_current)

    def test_active_financial_year_none_when_nothing_flagged(self):
        FinancialYear.objects.all().update(is_active=False)
        self.assertIsNone(active_financial_year())

    def test_public_holidays_between_is_inclusive(self):
        holidays = public_holidays_between(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(
            [h.name for h in holidays], ["Independence Day"]
        )

    def test_public_holidays_between_multiple_ordered_by_date(self):
        holidays = public_holidays_between(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(
            [h.name for h in holidays], ["Independence Day", "Christmas Day"]
        )

    def test_public_holidays_between_empty_range(self):
        holidays = public_holidays_between(date(2027, 1, 1), date(2027, 12, 31))
        self.assertEqual(list(holidays), [])


class FinancialYearEndpointTests(TestCase):
    """HR-only CRUD for financial-year periods."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )

        self.fy = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

        self.list_url = "/api/v1/financial-years/"
        self.detail_url = f"/api/v1/financial-years/{self.fy.id}/"

    def test_list_requires_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_and_update_require_authentication(self):
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(self.list_url, {}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_can_list_years_ordered_by_latest_start_first(self):
        FinancialYear.objects.create(
            start_date=date(2027, 7, 1),
            end_date=date(2028, 6, 30),
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        starts = [item["start_date"] for item in response.data["results"]]  # type: ignore[index]
        self.assertEqual(starts, ["2027-07-01", "2026-07-01"])

    def test_hr_can_retrieve_financial_year(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])  # type: ignore[index]

    def test_hr_can_create_inactive_financial_year(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "start_date": "2028-07-01",
                "end_date": "2029-06-30",
                "is_active": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            FinancialYear.objects.get(pk=response.data["id"]).is_active  # type: ignore[index]
        )

    def test_hr_can_update_dates(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            self.detail_url, {"end_date": "2027-09-30"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fy.refresh_from_db()
        self.assertEqual(self.fy.end_date, date(2027, 9, 30))

    def test_create_validates_missing_dates(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)  # type: ignore[index]
        self.assertIn("end_date", response.data)  # type: ignore[index]

    def test_end_date_before_start_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"start_date": "2028-07-01", "end_date": "2028-06-30"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)  # type: ignore[index]

    def test_overlapping_year_rejected_even_when_future_dated(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"start_date": "2027-01-01", "end_date": "2027-12-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)  # type: ignore[index]

    def test_adjacent_year_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"start_date": "2027-07-01", "end_date": "2028-06-30"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_activating_new_year_deactivates_the_previous(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "start_date": "2027-07-01",
                "end_date": "2028-06-30",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.fy.refresh_from_db()
        self.assertFalse(self.fy.is_active)
        self.assertTrue(
            FinancialYear.objects.get(pk=response.data["id"]).is_active  # type: ignore[index]
        )

    def test_patching_active_deactivates_previous(self):
        self.client.force_authenticate(user=self.hr_user)
        future = FinancialYear.objects.create(
            start_date=date(2027, 7, 1),
            end_date=date(2028, 6, 30),
        )
        response = self.client.patch(
            f"/api/v1/financial-years/{future.id}/", {"is_active": True}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fy.refresh_from_db()
        self.assertFalse(self.fy.is_active)
        future.refresh_from_db()
        self.assertTrue(future.is_active)

    def test_delete_not_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class PublicHolidayEndpointTests(TestCase):
    """HR-only CRUD for public holidays."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )

        self.holiday = PublicHoliday.objects.create(
            name="Independence Day", date=date(2026, 7, 6)
        )
        PublicHoliday.objects.create(
            name="Christmas Day", date=date(2026, 12, 25)
        )
        PublicHoliday.objects.create(
            name="New Year", date=date(2027, 1, 1)
        )

        self.list_url = "/api/v1/public-holidays/"
        self.detail_url = f"/api/v1/public-holidays/{self.holiday.id}/"

    def test_list_requires_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_and_update_require_authentication(self):
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(self.list_url, {}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_can_list_holidays_ordered_by_date(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]  # type: ignore[index]
        self.assertEqual(names, ["Independence Day", "Christmas Day", "New Year"])

    def test_hr_can_retrieve_holiday(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Independence Day")  # type: ignore[index]

    def test_hr_can_create_holiday(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"name": "Labour Day", "date": "2027-05-01"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PublicHoliday.objects.filter(name="Labour Day").count(), 1)

    def test_hr_can_update_holiday(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            self.detail_url, {"name": "Independence Day (Moved)"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.holiday.refresh_from_db()
        self.assertEqual(self.holiday.name, "Independence Day (Moved)")

    def test_blank_name_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, {"name": "  ", "date": "2027-05-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)  # type: ignore[index]

    def test_missing_date_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.list_url, {"name": "Labour Day"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date", response.data)  # type: ignore[index]

    def test_duplicate_date_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"name": "Duplicate", "date": "2026-07-06"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date", response.data)  # type: ignore[index]

    def test_year_filter(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url, {"year": "2027"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # type: ignore[index]
        self.assertEqual(response.data["results"][0]["name"], "New Year")  # type: ignore[index]

    def test_invalid_year_filter_returns_400_not_500(self):
        self.client.force_authenticate(user=self.hr_user)
        for bad in ("abc", "thirty", "4.5"):
            response = self.client.get(self.list_url, {"year": bad})
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, f"year={bad}"
            )

    def test_delete_not_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class FinancialYearAdminTests(TestCase):
    """Admin form applies overlap and single-active rules; no hard delete."""

    def setUp(self):
        self.fy = FinancialYear.objects.create(
            start_date=TODAY,
            end_date=TODAY + timedelta(days=364),
            is_active=True,
        )

    def _data(self, **overrides):
        data = {
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY + timedelta(days=364)).isoformat(),
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_form_rejects_overlapping_period(self):
        form = FinancialYearAdminForm(
            data=self._data(start_date=(TODAY + timedelta(days=100)).isoformat())
        )
        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)

    def test_form_allows_editing_the_same_period(self):
        form = FinancialYearAdminForm(
            data=self._data(end_date=(TODAY + timedelta(days=365)).isoformat()),
            instance=self.fy,
        )
        self.assertTrue(form.is_valid())

    def test_form_allows_non_overlapping_future_period(self):
        form = FinancialYearAdminForm(
            data=self._data(
                start_date=(TODAY + timedelta(days=365)).isoformat(),
                end_date=(TODAY + timedelta(days=729)).isoformat(),
            )
        )
        self.assertTrue(form.is_valid())

    def test_admin_save_model_deactivates_previous_active(self):
        other = FinancialYear(
            start_date=TODAY + timedelta(days=365),
            end_date=TODAY + timedelta(days=729),
            is_active=True,
        )
        model_admin = FinancialYearAdmin(FinancialYear, AdminSite())
        model_admin.save_model(request=None, obj=other, form=None, change=False)
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        self.fy.refresh_from_db()
        self.assertFalse(self.fy.is_active)

    def test_admin_does_not_allow_delete(self):
        model_admin = FinancialYearAdmin(FinancialYear, AdminSite())
        self.assertFalse(model_admin.has_delete_permission(request=None))


class PublicHolidayAdminTests(TestCase):
    """Admin form applies the unique-date rule and no hard delete."""

    def setUp(self):
        self.holiday = PublicHoliday.objects.create(
            name="Independence Day", date=date(2026, 7, 6)
        )

    def test_form_rejects_duplicate_date(self):
        form = PublicHolidayAdminForm(
            data={"name": "Duplicate", "date": self.holiday.date.isoformat()}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)

    def test_form_allows_updating_the_same_holiday(self):
        form = PublicHolidayAdminForm(
            data={"name": "Independence Day", "date": self.holiday.date.isoformat()},
            instance=self.holiday,
        )
        self.assertTrue(form.is_valid())

    def test_admin_does_not_allow_delete(self):
        model_admin = PublicHolidayAdmin(PublicHoliday, AdminSite())
        self.assertFalse(model_admin.has_delete_permission(request=None))
class WorkingDaysCalculationTest(TestCase):
    def test_monday_to_friday_returns_5(self):
        start = date(2026, 9, 14)  # Monday
        end = date(2026, 9, 18)  # Friday
        self.assertEqual(calculate_working_days(start, end), 5)

    def test_weekend_excluded(self):
        start = date(2026, 9, 12)  # Saturday
        end = date(2026, 9, 14)  # Monday
        self.assertEqual(calculate_working_days(start, end), 1)

    def test_full_week_returns_5(self):
        start = date(2026, 9, 14)  # Monday
        end = date(2026, 9, 20)  # Sunday
        self.assertEqual(calculate_working_days(start, end), 5)

    def test_single_weekend_day_returns_0(self):
        start = date(2026, 9, 12)  # Saturday
        end = date(2026, 9, 12)
        self.assertEqual(calculate_working_days(start, end), 0)

    def test_none_dates_returns_0(self):
        self.assertEqual(calculate_working_days(None, date(2026, 9, 14)), 0)
        self.assertEqual(calculate_working_days(date(2026, 9, 14), None), 0)

    def test_end_before_start_returns_0(self):
        start = date(2026, 9, 18)
        end = date(2026, 9, 14)
        self.assertEqual(calculate_working_days(start, end), 0)

    def test_two_weeks(self):
        start = date(2026, 9, 14)  # Monday
        end = date(2026, 9, 27)  # Sunday
        self.assertEqual(calculate_working_days(start, end), 10)


class LeaveApplicationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@luanar.mw", password="testpass123"
        )

    def test_create_draft(self):
        app = LeaveApplication.objects.create(employee=self.user)
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)
        self.assertIsNone(app.reference_number)

    def test_str_with_reference(self):
        app = LeaveApplication.objects.create(
            employee=self.user, reference_number="LUANAR-2026-00001"
        )
        self.assertIn("LUANAR-2026-00001", str(app))

    def test_str_without_reference(self):
        app = LeaveApplication.objects.create(employee=self.user)
        self.assertIn("Draft", str(app))


class LeaveApplicationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@luanar.mw", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@luanar.mw", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_application(self):
        response = self.client.post(
            "/api/v1/leave-applications/",
            {"leave_type_id": 1, "reason": "Family vacation"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "draft")
        self.assertIsNone(response.data["reference_number"])

    def test_list_own_applications(self):
        LeaveApplication.objects.create(employee=self.user, reason="Test 1")
        LeaveApplication.objects.create(employee=self.other_user, reason="Other")
        response = self.client.get("/api/v1/leave-applications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_cannot_access_other_user_application(self):
        app = LeaveApplication.objects.create(employee=self.other_user)
        response = self.client.get(f"/api/v1/leave-applications/{app.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_autosave_with_dates_recalculates_days(self):
        response = self.client.post(
            "/api/v1/leave-applications/",
            {"reason": "Test"},
            format="json",
        )
        app_id = response.data["id"]
        response = self.client.patch(
            f"/api/v1/leave-applications/{app_id}/",
            {"start_date": "2026-09-14", "end_date": "2026-09-18"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["calculated_days"], 5)

    def test_cannot_edit_submitted_application(self):
        app = LeaveApplication.objects.create(
            employee=self.user,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-00001",
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            reason="Test",
        )
        response = self.client.patch(
            f"/api/v1/leave-applications/{app.id}/",
            {"reason": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_draft(self):
        app = LeaveApplication.objects.create(employee=self.user)
        response = self.client.delete(f"/api/v1/leave-applications/{app.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LeaveApplication.objects.filter(id=app.id).exists())

    def test_cannot_delete_submitted_application(self):
        app = LeaveApplication.objects.create(
            employee=self.user,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-00001",
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            reason="Test",
        )
        response = self.client.delete(f"/api/v1/leave-applications/{app.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_days(self):
        response = self.client.post(
            "/api/v1/leave-applications/preview-days/",
            {"start_date": "2026-09-14", "end_date": "2026-09-18"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 5)

    def test_preview_days_missing_dates(self):
        response = self.client.post(
            "/api/v1/leave-applications/preview-days/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bogus_calculated_days_is_ignored(self):
        response = self.client.post(
            "/api/v1/leave-applications/",
            {"reason": "Test", "calculated_days": 999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["calculated_days"])


class SupportingDocumentAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@luanar.mw", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            reason="Test",
        )

    def test_list_documents(self):
        response = self.client.get(
            f"/api/v1/leave-applications/{self.app.id}/documents/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_upload_to_submitted_application(self):
        self.app.status = LeaveApplication.Status.SUBMITTED
        self.app.reference_number = "LUANAR-2026-00001"
        self.app.save()
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        response = self.client.post(
            f"/api/v1/leave-applications/{self.app.id}/documents/",
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "application_not_editable")

    def test_upload_to_unknown_application_returns_404(self):
        from uuid import uuid4

        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        response = self.client.post(
            f"/api/v1/leave-applications/{uuid4()}/documents/",
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_to_foreign_application_returns_404(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        other = User.objects.create_user(
            username="other", email="other@luanar.mw", password="testpass123"
        )
        foreign = LeaveApplication.objects.create(employee=other, leave_type_id=1)
        file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        response = self.client.post(
            f"/api/v1/leave-applications/{foreign.id}/documents/",
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_over_size_limit_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with mock.patch("leave.documents.services.MAX_DOCUMENT_SIZE", 100):
            file = SimpleUploadedFile(
                "big.pdf", b"x" * 101, content_type="application/pdf"
            )
            response = self.client.post(
                f"/api/v1/leave-applications/{self.app.id}/documents/",
                {"file": file},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_with_unsupported_content_type_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile(
            "payload.exe", b"MZ", content_type="application/x-msdownload"
        )
        response = self.client.post(
            f"/api/v1/leave-applications/{self.app.id}/documents/",
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UnauthenticatedAccessTest(TestCase):
    def test_unauthenticated_list(self):
        client = APIClient()
        response = client.get("/api/v1/leave-applications/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_preview_days(self):
        client = APIClient()
        response = client.post(
            "/api/v1/leave-applications/preview-days/",
            {"start_date": "2026-09-14", "end_date": "2026-09-18"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SupportingDocumentSerializationTest(TestCase):
    """file_url is re-signed from file_path at read time, never the stored URL."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@luanar.mw", password=SEED_PASSWORD
        )
        self.app = LeaveApplication.objects.create(employee=self.user)
        self.doc = SupportingDocument.objects.create(
            application=self.app,
            file_path="leave-documents/abcd/notes.pdf",
            file_url="stale://signed-url",
            file_name="notes.pdf",
            file_size=1024,
            content_type="application/pdf",
        )

    def test_file_url_is_re_signed_from_file_path(self):
        with mock.patch(
            "leave.serializers.safe_signed_document_url",
            return_value="fresh://signed-url",
        ) as signed:
            data = SupportingDocumentSerializer(self.doc).data
        signed.assert_called_once_with("leave-documents/abcd/notes.pdf", fallback=self.doc.file_url)
        self.assertEqual(data["file_url"], "fresh://signed-url")

    def test_serialization_falls_back_to_stored_url_when_storage_unconfigured(self):
        with mock.patch(
            "leave.services.storage.signed_document_url",
            side_effect=ValueError("Supabase credentials are not configured."),
        ):
            data = SupportingDocumentSerializer(self.doc).data
        self.assertEqual(data["file_url"], "stale://signed-url")

    def test_serialization_falls_back_to_stored_url_when_object_missing(self):
        """A missing storage object (404) must not 500 the document list."""
        from storage3.exceptions import StorageApiError

        with mock.patch(
            "leave.services.storage.signed_document_url",
            side_effect=StorageApiError("Object not found", code="404", status=404),
        ):
            data = SupportingDocumentSerializer(self.doc).data
        self.assertEqual(data["file_url"], "stale://signed-url")

    def test_fresh_signature_is_derived_from_the_path(self):
        class _FakeBucket:
            def create_signed_url(self, path, expiry):
                return {"signedURL": f"https://signed/{path}?exp={expiry}"}

        class _FakeBucketClient:
            def from_(self, bucket):
                return _FakeBucket()

        class _FakeClient:
            def __init__(self):
                self.storage = _FakeBucketClient()

        with mock.patch(
            "leave.services.storage.get_supabase_client",
            return_value=_FakeClient(),
        ):
            data = SupportingDocumentSerializer(self.doc).data
        self.assertIn(
            "https://signed/leave-documents/abcd/notes.pdf", data["file_url"]
        )

    def test_stored_url_is_never_used_for_serialization(self):
        with mock.patch(
            "leave.serializers.safe_signed_document_url",
            return_value="fresh://signed-url",
        ):
            data = SupportingDocumentSerializer(self.doc).data
        self.assertNotIn("stale://signed-url", data["file_url"])


class DocumentStorageTest(TestCase):
    """Uploaded document keys are sanitized and collision-safe."""

    def test_upload_uses_sanitized_collision_safe_key(self):
        captured = {}

        class _FakeBucket:
            def upload(self, path, data, opts):
                captured["path"] = path

            def create_signed_url(self, path, expiry):
                return {"signedURL": f"https://signed/{path}"}

        class _FakeBucketClient:
            def from_(self, bucket):
                return _FakeBucket()

        class _FakeClient:
            def __init__(self):
                self.storage = _FakeBucketClient()

        from django.core.files.uploadedfile import SimpleUploadedFile
        from uuid import uuid4

        app_id = str(uuid4())
        with mock.patch(
            "leave.services.storage.get_supabase_client",
            return_value=_FakeClient(),
        ):
            file = SimpleUploadedFile(
                "../../Budget Plan (2).pdf", b"%PDF", content_type="application/pdf"
            )
            result = upload_document(file, app_id)

        path = captured["path"]
        self.assertTrue(path.startswith(f"leave-documents/{app_id}/"))
        name = path.replace(f"leave-documents/{app_id}/", "")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)
        token, _, base = name.partition("-")
        self.assertEqual(len(token), 32)
        self.assertEqual(base, "Budget_Plan__2_.pdf")
        self.assertEqual(result["path"], path)
        self.assertEqual(result["url"], f"https://signed/{path}")
