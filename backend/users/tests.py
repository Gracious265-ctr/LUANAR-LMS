from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import EmployeeProfile, User

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
        self.employee_profile = EmployeeProfile.objects.create(
            user=self.employee_user,
            designation="Administrative Officer",
            department="Administration",
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
        self.assertEqual(response.data["department"], "Administration")  # type: ignore[index]
        self.assertEqual(response.data["grade"], "B")  # type: ignore[index]
        self.assertEqual(  # type: ignore[index]
            response.data["category"], EmployeeProfile.Category.ADMINISTRATION
        )

    def test_create_new_employee_creates_linked_user_with_unusable_password(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "new.employee@test.luanar",
                "first_name": "New",
                "last_name": "Employee",
                "designation": "Lecturer",
                "department": "Bunda College",
                "category": "academic",
                "grade": "C",
                "appointment_date": "2023-05-01",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(EmployeeProfile.objects.filter(user__email="new.employee@test.luanar").exists())
        user = User.objects.get(email="new.employee@test.luanar")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.role, User.Role.EMPLOYEE)

    def test_create_links_existing_user_by_email(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "email": "employee@test.luanar",
                "first_name": "Ignored",
                "last_name": "Name",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(  # type: ignore[index]
            response.data["email"][0],
            "An employee record for this email already exists.",
        )

    def test_create_existing_email_without_profile_links_user(self):
        supervisor = User.objects.create_user(
            username="supervisor@test.luanar",
            email="supervisor@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Supervisor",
            role=User.Role.SUPERVISOR,
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"email": "supervisor@test.luanar"},
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
        response = self.client.patch(
            self.detail_url,
            {
                "first_name": "Updated",
                "department": "Faculty of Agriculture",
                "grade": "H",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee_user.refresh_from_db()
        self.employee_profile.refresh_from_db()
        self.assertEqual(self.employee_user.first_name, "Updated")
        self.assertEqual(self.employee_profile.department, "Faculty of Agriculture")
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
            department="Bunda College",
            designation="Lecturer",
            grade="E",
        )
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get(self.list_url, {"search": "Bunda"})
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

    def test_hard_delete_not_allowed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
