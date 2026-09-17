import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import LeaveApplication, ReferenceSequence, SupportingDocument
from .services.working_days import calculate_working_days

User = get_user_model()


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

    def test_submit_draft(self):
        app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            reason="Family matters",
        )
        response = self.client.post(
            f"/api/v1/leave-applications/{app.id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reference_number", response.data)
        self.assertTrue(response.data["reference_number"].startswith("LUANAR-2026-"))
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertIsNotNone(app.submitted_at)

    def test_submit_with_missing_fields(self):
        app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            # reason is missing
        )
        response = self.client.post(
            f"/api/v1/leave-applications/{app.id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data["detail"])

    def test_submit_already_submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date="2026-09-14",
            end_date="2026-09-18",
            reason="Family matters",
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-00001",
        )
        response = self.client.post(
            f"/api/v1/leave-applications/{app.id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reference_numbers_are_sequential(self):
        for i in range(3):
            app = LeaveApplication.objects.create(
                employee=self.user,
                leave_type_id=1,
                start_date="2026-09-14",
                end_date="2026-09-18",
                reason=f"Reason {i}",
            )
            self.client.post(
                f"/api/v1/leave-applications/{app.id}/submit/",
                format="json",
            )
        apps = LeaveApplication.objects.filter(
            status=LeaveApplication.Status.SUBMITTED
        ).order_by("submitted_at")
        refs = [a.reference_number for a in apps]
        self.assertEqual(len(set(refs)), 3)

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
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
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
