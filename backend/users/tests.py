"""HR-facing account, employee-record, and bootstrap endpoint tests.

The department suite that used to live here — ``DepartmentViewSet``, the
``/api/v1/departments/`` endpoints, create/rename/retire, the team and employee
counts each department reported, and department search/ordering — was removed
along with the model. There is no department feature left to test, so those
tests are gone rather than rewritten; where an employee test only needed *some*
organisational placement it now uses a :class:`~workflows.models.Team`.
"""

from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from audit.models import AuditEntry
from .models import EmployeeProfile, User
from workflows.models import CampusRoleAssignment, TeamRoleAssignment
from workflows.testing import (
    create_user_with_role,
    grant_approver_role,
    make_approver,
    make_employee,
    make_team,
    team_for,
)

SEED_PASSWORD = "testpass123"


class AuthEndpointTests(TestCase):
    """Test the authentication endpoints."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )

    def test_login_success(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "employee@test.luanar", "password": SEED_PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)  # type: ignore[union-attr]
        self.assertIn("refresh", response.data)  # type: ignore[union-attr]

    def test_login_wrong_password(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "employee@test.luanar", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_unauthenticated(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "employee@test.luanar")  # type: ignore[index]
        self.assertEqual(response.data["role"], User.Role.EMPLOYEE)  # type: ignore[index]

    def test_me_returns_correct_role(self):
        admin_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        self.client.force_authenticate(user=admin_user)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], User.Role.HR)  # type: ignore[index]

    def test_refresh_token(self):
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "employee@test.luanar", "password": SEED_PASSWORD},
        )
        refresh_token = login_response.data["refresh"]  # type: ignore[index]

        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": refresh_token},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)  # type: ignore[union-attr]

    def test_refresh_invalid_token(self):
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": "invalid-token"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmployeeEndpointTests(TestCase):
    """HR-only CRUD for employee records."""

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
        self.administration = team_for("Administration Team")
        self.employee_profile = EmployeeProfile.objects.create(
            user=self.employee_user,
            designation="Administrative Officer",
            team=self.administration,
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
            appointment_date=date(2020, 1, 15),
        )
        self.list_url = "/api/v1/employees/"
        self.detail_url = f"/api/v1/employees/{self.employee_profile.id}/"

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_requires_authentication(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_requires_authentication(self):
        response = self.client.patch(self.detail_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_hr_role_forbidden_detail(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.patch(self.detail_url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_can_list_employees(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)  # type: ignore[index]
        result = response.data["results"][0]  # type: ignore[index]
        self.assertEqual(result["email"], "employee@test.luanar")
        self.assertEqual(result["full_name"], "Test Employee")
        self.assertEqual(result["role"], User.Role.EMPLOYEE)
        self.assertTrue(result["is_active"])

    def test_hr_can_retrieve_employee(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(  # type: ignore[index]
            response.data["team"], self.administration.pk
        )
        self.assertEqual(  # type: ignore[index]
            response.data["team_name"], "Administration Team"
        )
        self.assertEqual(response.data["grade"], "B")  # type: ignore[index]
        self.assertEqual(  # type: ignore[index]
            response.data["category"], EmployeeProfile.Category.ADMINISTRATION
        )

    def test_create_new_employee_is_issued_without_a_usable_password(self):
        """HR is not the source of credentials: no password is set here.

        The account is created with an unusable password and a set-password link
        is queued to the address on file. ``tests_password_set`` covers that flow
        end to end; what matters on this endpoint is that HR's create returns
        201 and leaves the account unable to sign in until the link is used.
        """
        self.client.force_authenticate(user=self.hr_user)
        bunda = team_for("Bunda College Team")
        response = self.client.post(
            self.list_url,
            {
                "email": "new.employee@test.luanar",
                "first_name": "New",
                "last_name": "Employee",
                "designation": "Lecturer",
                "team": bunda.pk,
                "category": "academic",
                "grade": "C",
                "appointment_date": "2023-05-01",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new.employee@test.luanar")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.username, "new.employee@test.luanar")
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(profile.team, bunda)
        self.assertNotIn("password", response.data)  # type: ignore[operator]

    def test_create_ignores_a_supplied_password(self):
        """A password in the payload is refused rather than quietly honoured.

        Silently accepting one would let an administrator believe they had set
        somebody's credential through a field that no longer sets anything.
        """
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "ignored-pass@test.luanar",
                "first_name": "Ignored",
                "last_name": "Password",
                "password": "supplied-pass-123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="ignored-pass@test.luanar")
        self.assertFalse(user.has_usable_password())

    def test_create_links_existing_user_by_email(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "employee@test.luanar",
                "first_name": "Ignored",
                "last_name": "Name",
                "password": "initial-pass-123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(  # type: ignore[index]
            response.data["email"][0],
            "An employee record for this email already exists.",
        )

    def test_create_existing_email_without_profile_links_user(self):
        supervisor = create_user_with_role(
            username="supervisor@test.luanar",
            email="supervisor@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Supervisor",
            role="supervisor",
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"email": "supervisor@test.luanar", "password": "initial-pass-123"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeProfile.objects.get(user=supervisor).user, supervisor)
        self.assertEqual(User.objects.count(), 3)

    def test_create_requires_email(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.list_url, {"first_name": "No", "last_name": "Email"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_changes_profile_and_user(self):
        self.client.force_authenticate(user=self.hr_user)
        agriculture = team_for("Agriculture Team")
        response = self.client.patch(
            self.detail_url,
            {
                "first_name": "Updated",
                "team": agriculture.pk,
                "grade": "H",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.employee_profile.refresh_from_db()
        self.assertEqual(self.employee_user.first_name, "Updated")
        self.assertEqual(self.employee_profile.team, agriculture)
        self.assertEqual(self.employee_profile.grade, "H")

    def test_update_email_renames_user(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            self.detail_url,
            {"email": "renamed.employee@test.luanar"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.email, "renamed.employee@test.luanar")
        self.assertEqual(self.employee_user.username, "renamed.employee@test.luanar")

    def test_update_email_conflict_rejected(self):
        other = User.objects.create_user(
            username="other@test.luanar",
            email="other@test.luanar",
            password=SEED_PASSWORD,
            first_name="Other",
            last_name="User",
            role=User.Role.EMPLOYEE,
        )
        EmployeeProfile.objects.create(user=other)
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"email": "other@test.luanar"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deactivation_toggles_linked_user(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"is_active": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.assertFalse(self.employee_user.is_active)

        response = self.client.patch(self.detail_url, {"is_active": True})
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.is_active)

    def test_search_filters_employees(self):
        other = User.objects.create_user(
            username="zoe@test.luanar",
            email="zoe@test.luanar",
            password=SEED_PASSWORD,
            first_name="Zoe",
            last_name="Lecturer",
            role=User.Role.EMPLOYEE,
        )
        EmployeeProfile.objects.create(
            user=other,
            team=team_for("Bunda College Team"),
            designation="Lecturer",
            grade="E",
        )
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get(self.list_url, {"search": "Lecturer"})
        self.assertEqual(response.data["count"], 1)  # type: ignore[index]
        self.assertEqual(  # type: ignore[index]
            response.data["results"][0]["email"], "zoe@test.luanar"  # type: ignore[index]
        )

        response = self.client.get(self.list_url, {"search": "employee@test.luanar"})
        self.assertEqual(response.data["count"], 1)  # type: ignore[index]

    def test_ordering_sorts_employees(self):
        other = User.objects.create_user(
            username="zoe@test.luanar",
            email="zoe@test.luanar",
            password=SEED_PASSWORD,
            first_name="Zoe",
            last_name="Lecturer",
            role=User.Role.EMPLOYEE,
        )
        EmployeeProfile.objects.create(user=other)
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get(self.list_url, {"ordering": "user__first_name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [r["first_name"] for r in response.data["results"]]  # type: ignore[index]
        self.assertEqual(names, ["Test", "Zoe"])

    def test_a_new_employee_cannot_be_created_as_an_approver(self):
        """Approver access follows from configuration, never from the account.

        A new employee is a normal employee. Handing somebody the approval desk at
        creation would make them look authoritative before HR had appointed them
        to anything — and would let one role be held with no appointment behind
        it, which is the thing the whole section model exists to prevent.
        """
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "managed@test.luanar",
                "first_name": "Managed",
                "last_name": "Supervisor",
                "password": "initial-pass-123",
                "role": User.Role.APPROVER,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)  # type: ignore[arg-type]
        self.assertFalse(
            User.objects.filter(email="managed@test.luanar").exists()
        )

    def test_hr_cannot_create_another_hr_account(self):
        """Only an administrator grants HR reach.

        HR is the account that administers everyone else, so letting it mint
        more HR accounts would make the privilege self-propagating. An
        administrator creates HR accounts in the Django admin instead.
        """
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "second.hr@test.luanar",
                "first_name": "Second",
                "last_name": "HR",
                "password": "initial-pass-123",
                "role": User.Role.HR,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)  # type: ignore[arg-type]
        self.assertFalse(
            User.objects.filter(email="second.hr@test.luanar").exists()
        )

    def test_hr_can_place_employee_on_a_team(self):
        team = make_team("Science team", ("supervisor", "hod"))
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "placed@test.luanar",
                "first_name": "Placed",
                "last_name": "Employee",
                "password": "initial-pass-123",
                "team": team.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = EmployeeProfile.objects.get(user__email="placed@test.luanar")
        self.assertEqual(profile.team, team)
        self.assertEqual(response.data["team"], team.pk)  # type: ignore[index]
        self.assertEqual(response.data["team_name"], "Science team")  # type: ignore[index]

    def test_approver_roles_reports_the_positions_a_person_holds(self):
        """The employee list answers "who can approve for this person".

        The two facts are separate: granting an approver role shows up here
        while the system ``role`` stays ``employee``, because access to the
        approval desk is not the same as a place in a chain.
        """
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(
            self.client.get(self.detail_url).data["approver_roles"], []
        )

        grant_approver_role(self.employee_user, "dean")

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["approver_roles"], ["dean"]  # type: ignore[index]
        )
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.role, User.Role.EMPLOYEE)

    def test_a_hr_created_employee_holds_no_approver_roles(self):
        """A brand-new employee account cannot approve anything yet.

        Not because it starts inactive — it does not, and that used to be an
        accident of form-encoded requests being read as ``is_active=false`` —
        but because holding a position is a separate fact from existing. The
        account has no role assignment until HR puts them on a team.
        """
        grant_approver_role(self.hr_user, "dean")
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "pending@test.luanar",
                "first_name": "Pend",
                "last_name": "Ing",
                "password": "initial-pass-123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_active"])  # type: ignore[index]
        self.assertEqual(response.data["approver_roles"], [])  # type: ignore[index]

    def test_a_deactivated_employee_holds_no_approver_roles(self):
        """Deactivation is what takes an existing holder out of the chain."""
        grant_approver_role(self.employee_user, "dean")
        self.client.force_authenticate(user=self.hr_user)
        before = self.client.get(self.detail_url)
        self.assertEqual(before.data["approver_roles"], ["dean"])  # type: ignore[index]

        self.client.patch(self.detail_url, {"is_active": False})

        after = self.client.get(self.detail_url)
        self.assertFalse(after.data["is_active"])  # type: ignore[index]
        self.assertEqual(after.data["approver_roles"], [])  # type: ignore[index]

    def test_placing_an_employee_on_a_team_is_audited(self):
        team = make_team("Audit team", ("supervisor",))
        self.client.force_authenticate(user=self.hr_user)
        self.client.patch(self.detail_url, {"team": team.pk})
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=str(self.employee_profile.id),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertEqual(entry.detail["after"]["team"], team.pk)

    def test_create_without_role_defaults_to_employee(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "default-role@test.luanar",
                "first_name": "Default",
                "last_name": "Role",
                "password": "initial-pass-123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="default-role@test.luanar")
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertEqual(response.data["role"], User.Role.EMPLOYEE)  # type: ignore[index]

    def test_create_with_blank_role_defaults_to_employee(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "blank-role@test.luanar",
                "first_name": "Blank",
                "last_name": "Role",
                "password": "initial-pass-123",
                "role": "",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="blank-role@test.luanar")
        self.assertEqual(user.role, User.Role.EMPLOYEE)

    def test_create_rejects_invalid_role(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "invalid-role@test.luanar",
                "first_name": "Invalid",
                "last_name": "Role",
                "password": "initial-pass-123",
                "role": "not-a-role",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)  # type: ignore[arg-type]
        self.assertFalse(
            User.objects.filter(email="invalid-role@test.luanar").exists()
        )

    def test_hr_cannot_promote_an_employee_to_approver(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"role": User.Role.APPROVER})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)  # type: ignore[arg-type]
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.role, User.Role.EMPLOYEE)

    def test_hr_cannot_promote_an_employee_to_hr(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"role": User.Role.HR})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.role, User.Role.EMPLOYEE)

    def test_update_without_role_keeps_existing_role(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"designation": "Senior Officer"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.role, User.Role.EMPLOYEE)

    def test_an_unchanged_role_is_still_accepted(self):
        """An existing HR account can be edited without tripping the role rule.

        The rule refuses a *change* to approver/hr, not the value that is
        already on the row, so saving the profile of an HR account does not
        need its role stripped first.
        """
        hr_profile = EmployeeProfile.objects.create(user=self.hr_user)
        detail = f"/api/v1/employees/{hr_profile.id}/"
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            detail, {"role": User.Role.HR, "designation": "HR Manager"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertEqual(self.hr_user.role, User.Role.HR)

    def test_update_ignores_a_password_field_entirely(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(self.detail_url, {"password": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.check_password(SEED_PASSWORD))

    def test_a_password_reset_is_not_written_into_the_audit_detail(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.patch(self.detail_url, {"password": "a-new-password-1"})
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=str(self.employee_profile.id),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertNotIn("password", entry.detail.get("after", {}))
        self.assertNotIn("password", entry.detail.get("changed", {}))

    def test_hard_delete_not_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class EmployeeSerializerAtomicityTests(TestCase):
    """A failed audit write rolls back employee create and update."""

    def setUp(self):
        from rest_framework.test import APIRequestFactory

        self.hr = User.objects.create_user(
            username="hr-atomic@test.luanar",
            email="hr-atomic@test.luanar",
            password="testpass123",
            role=User.Role.HR,
        )
        self.request = APIRequestFactory().post("/")
        self.request.user = self.hr

    def _serializer(self, *args, **kwargs):
        from unittest import mock

        from .serializers import EmployeeSerializer

        return EmployeeSerializer(*args, context={"request": self.request}, **kwargs)

    def test_create_rolls_back_user_and_profile_when_audit_fails(self):
        from unittest import mock

        serializer = self._serializer(
            data={
                "email": "rollback-create@test.luanar",
                "first_name": "Roll",
                "last_name": "Back",
                "password": "initial-pass-123",
                "designation": "Lecturer",
            }
        )
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "users.serializers.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        self.assertFalse(
            User.objects.filter(email="rollback-create@test.luanar").exists()
        )

    def test_update_rolls_back_profile_when_audit_fails(self):
        from unittest import mock

        profile = EmployeeProfile.objects.create(
            user=self.hr,
            designation="Lecturer",
            team=team_for("Computer Science Team"),
        )
        serializer = self._serializer(
            profile,
            data={"email": self.hr.email, "designation": "Senior Lecturer"},
        )
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "users.serializers.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        profile.refresh_from_db()
        self.assertEqual(profile.designation, "Lecturer")

    def test_create_with_hr_role_is_refused_before_any_write(self):
        """The escalation rule stops the write at validation, not after it.

        Refusing here means no user row is ever created for a request that
        asked to mint another HR account — there is nothing to roll back.
        """
        serializer = self._serializer(
            data={
                "email": "rollback-create-role@test.luanar",
                "first_name": "Roll",
                "last_name": "Back",
                "password": "initial-pass-123",
                "role": User.Role.HR,
                "designation": "Lecturer",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("role", serializer.errors)
        self.assertFalse(
            User.objects.filter(email="rollback-create-role@test.luanar").exists()
        )

    def test_update_with_role_escalation_is_refused(self):
        employee = User.objects.create_user(
            username="rollback-update-role@test.luanar",
            email="rollback-update-role@test.luanar",
            password="testpass123",
            first_name="Roll",
            last_name="Back",
            role=User.Role.EMPLOYEE,
        )
        profile = EmployeeProfile.objects.create(
            user=employee,
            designation="Lecturer",
            team=team_for("Computer Science Team"),
        )
        serializer = self._serializer(
            profile,
            data={"role": User.Role.APPROVER, "designation": "Senior Lecturer"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("role", serializer.errors)
        employee.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(employee.role, User.Role.EMPLOYEE)
        self.assertEqual(profile.designation, "Lecturer")

    def test_update_rolls_back_a_password_reset_when_audit_fails(self):
        from unittest import mock

        employee = User.objects.create_user(
            username="rollback-password@test.luanar",
            email="rollback-password@test.luanar",
            password="testpass123",
            first_name="Roll",
            last_name="Back",
            role=User.Role.EMPLOYEE,
        )
        profile = EmployeeProfile.objects.create(user=employee)
        serializer = self._serializer(
            profile,
            data={
                "email": employee.email,
                "password": "a-new-password-1",
                "designation": "Senior Lecturer",
            },
        )
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "users.serializers.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        employee.refresh_from_db()
        self.assertTrue(employee.check_password("testpass123"))


class AdminUserEndpointTests(TestCase):
    """Superuser-only provisioning of HR accounts.

    This is the front door into a fresh database: there is no HR user until the
    superuser makes one here, and no HR means nobody can reach the back office to
    create the rest of the configuration.
    """

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.superuser = User.objects.create_superuser(
            username="root@test.luanar",
            email="root@test.luanar",
            password=SEED_PASSWORD,
        )
        self.hr_user = User.objects.create_user(
            username="hr-admin-users@test.luanar",
            email="hr-admin-users@test.luanar",
            password=SEED_PASSWORD,
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            username="emp-admin-users@test.luanar",
            email="emp-admin-users@test.luanar",
            password=SEED_PASSWORD,
            role=User.Role.EMPLOYEE,
        )
        self.list_url = "/api/v1/admin-users/"

    def test_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_non_superuser_is_forbidden(self):
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.post(self.list_url, {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_superuser_lists_only_hr_accounts(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.data["results"]}  # type: ignore[index]
        self.assertEqual(emails, {"hr-admin-users@test.luanar"})

    def test_superuser_creates_an_hr_account(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.list_url,
            {
                "first_name": "Ada",
                "last_name": "Person",
                "email": "ada@test.luanar",
                "password": "longenough",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="ada@test.luanar")
        self.assertEqual(created.role, User.Role.HR)
        self.assertEqual(created.username, "ada@test.luanar")
        self.assertTrue(created.check_password("longenough"))
        self.assertFalse(created.is_superuser)

    def test_create_requires_a_password(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.list_url, {"email": "nopass@test.luanar"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)  # type: ignore[arg-type]

    def test_a_short_password_is_refused(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.list_url,
            {"email": "short@test.luanar", "password": "short"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)  # type: ignore[arg-type]

    def test_create_cannot_choose_a_role_or_mint_a_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.list_url,
            {
                "email": "sneaky@test.luanar",
                "password": "longenough",
                "role": User.Role.HR,
                "is_superuser": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="sneaky@test.luanar")
        self.assertEqual(created.role, User.Role.HR)
        self.assertFalse(created.is_superuser)

    def test_a_duplicate_email_is_refused(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(
            self.list_url,
            {"email": "hr-admin-users@test.luanar", "password": "longenough"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)  # type: ignore[arg-type]

    def test_superuser_resets_a_password(self):
        self.client.force_authenticate(user=self.superuser)
        detail = f"{self.list_url}{self.hr_user.pk}/"
        response = self.client.patch(detail, {"password": "brandnewpass"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertTrue(self.hr_user.check_password("brandnewpass"))

    def test_a_blank_password_keeps_the_current_one(self):
        self.client.force_authenticate(user=self.superuser)
        detail = f"{self.list_url}{self.hr_user.pk}/"
        response = self.client.patch(detail, {"first_name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertEqual(self.hr_user.first_name, "Renamed")
        self.assertTrue(self.hr_user.check_password(SEED_PASSWORD))

    def test_role_cannot_be_changed_through_this_endpoint(self):
        self.client.force_authenticate(user=self.superuser)
        detail = f"{self.list_url}{self.hr_user.pk}/"
        response = self.client.patch(detail, {"role": User.Role.EMPLOYEE})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertEqual(self.hr_user.role, User.Role.HR)

    def test_superuser_can_deactivate_an_hr_account(self):
        self.client.force_authenticate(user=self.superuser)
        detail = f"{self.list_url}{self.hr_user.pk}/"
        response = self.client.patch(detail, {"is_active": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertFalse(self.hr_user.is_active)

    def test_an_employee_is_not_visible_through_this_endpoint(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f"{self.list_url}{self.employee_user.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EmployeeRosterFilterTests(TestCase):
    """The employees endpoint's roster-picker filters.

    The team screen's member picker asks ``?team=none`` and scopes the answer by
    the team's own category — an academic team takes academic employees, an
    administration team takes administration employees — and by who already
    serves it as a wide approver (institution-wide, team-wide on that team, or
    campus-wide at its campus): an approver is managed on the Approvers tab, not
    placed on the roster. The write path enforces the same two rules; these are
    the read half, so a picker offers exactly the people it may add.
    """

    LIST_URL = "/api/v1/employees/"

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = User.objects.create_user(
            username="roster-hr@test.luanar",
            email="roster-hr@test.luanar",
            password=SEED_PASSWORD,
            role=User.Role.HR,
        )
        self.client.force_authenticate(self.hr_user)
        self.academic = make_employee(
            "academic-candidate@test.luanar",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        self.admin = make_employee(
            "admin-candidate@test.luanar",
            category=EmployeeProfile.Category.ADMINISTRATION,
        )

    def emails(self, response) -> set[str]:
        return {row["email"] for row in response.data["results"]}  # type: ignore[index]

    def test_academic_category_returns_only_academic_employees(self):
        response = self.client.get(
            f"{self.LIST_URL}?team=none&category=academic"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.academic.email, self.emails(response))
        self.assertNotIn(self.admin.email, self.emails(response))

    def test_administration_category_returns_only_administration_employees(self):
        response = self.client.get(
            f"{self.LIST_URL}?team=none&category=administration"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.admin.email, self.emails(response))
        self.assertNotIn(self.academic.email, self.emails(response))

    def test_an_unknown_category_is_ignored_not_fatal(self):
        response = self.client.get(
            f"{self.LIST_URL}?team=none&category=no-such-category"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.academic.email, self.emails(response))
        self.assertIn(self.admin.email, self.emails(response))

    def test_institution_wide_approver_is_kept_out_but_only_for_that_team(self):
        registrar = make_approver(
            "registrar",
            username="roster-registrar@test.luanar",
            institution_wide=True,
        )
        team = team_for("Roster Team")
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team={team.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(registrar.email, self.emails(response))
        # Without the filter the same person is offered again: the exclusion is
        # per team, not a hide-an-approver-everywhere rule.
        plain = self.client.get(f"{self.LIST_URL}?team=none")
        self.assertIn(registrar.email, self.emails(plain))

    def test_team_wide_approver_is_kept_out_of_that_team_roster(self):
        role = grant_approver_role(self.academic, "hod", institution_wide=False)
        team = team_for("Roster Team")
        TeamRoleAssignment.objects.create(team=team, role=role, user=self.academic)
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team={team.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.academic.email, self.emails(response))
        self.assertIn(self.admin.email, self.emails(response))

    def test_campus_wide_approver_is_kept_out_of_an_academic_team_roster(self):
        academic_team = make_team(
            "Roster Academic Team", ["supervisor"], campus="Roster Campus"
        )
        campus_role = grant_approver_role(
            self.academic, "campus_registrar", institution_wide=False
        )
        CampusRoleAssignment.objects.create(
            campus=academic_team.campus,
            role=campus_role,
            user=self.academic,
        )
        self.assertTrue(academic_team.category == EmployeeProfile.Category.ACADEMIC)
        # A campus-wide holding is invisible anywhere outside the holding campus's
        # teams: query for a different team and the person is still a candidate.
        other_team = team_for("Roster Other Team")
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team={other_team.pk}"
        )
        self.assertIn(self.academic.email, self.emails(response))
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team={academic_team.pk}"
        )
        self.assertNotIn(self.academic.email, self.emails(response))

    def test_a_missing_team_or_garbage_id_ignores_the_wide_filter(self):
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team=999999"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.academic.email, self.emails(response))
        response = self.client.get(
            f"{self.LIST_URL}?team=none&not_wide_for_team=not-a-number"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.academic.email, self.emails(response))
