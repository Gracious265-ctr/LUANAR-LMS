from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import User

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
