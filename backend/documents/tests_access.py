"""The documents hub's read scope: employee, team manager, HR.

Both hub lists resolve the viewer through ``documents.access.visible_employee_ids``.
These drive that one predicate through the two routes end to end, so the two
lists cannot drift apart: a plain employee sees only their own documents, a team
manager adds the employees on the teams they manage *and* themselves, and HR
sees the institution.
"""

from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import ApprovedLeaveDocument
from leave.models import LeaveApplication, SupportingDocument
from teams.models import TeamRoleAssignment
from users.models import EmployeeProfile

from workflows.testing import ensure_roles, make_team

User = get_user_model()

SUPPORTING_URL = "/api/v1/documents/supporting/"
APPROVED_URL = "/api/v1/documents/approved/"


def _application(employee):
    return LeaveApplication.objects.create(
        employee=employee,
        leave_type_id=1,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 6),
        reason="Test",
        status=LeaveApplication.Status.APPROVED,
    )


def _supporting(application, name="letter.pdf", **kwargs):
    return SupportingDocument.objects.create(
        application=application,
        file_path=f"leave-documents/{application.id}/{name}",
        file_url=f"https://stored/{name}",
        file_name=name,
        file_size=1024,
        content_type="application/pdf",
        **kwargs,
    )


def _approved(application, name="approved-leave.pdf"):
    return ApprovedLeaveDocument.objects.create(
        application=application,
        status=ApprovedLeaveDocument.Status.READY,
        file_path=f"approved/{application.id}/{name}",
        file_url=f"https://stored/{name}",
        file_name=name,
        file_size=2048,
        content_type="application/pdf",
    )


class DocumentsHubScopeTests(TestCase):
    """Each viewer's two lists cover exactly the employees they may read."""

    def setUp(self):
        self.client = APIClient()
        # Signing is enrichment, not the row: pin it so the approved payload is
        # deterministic instead of depending on whether Supabase is configured.
        patcher = mock.patch(
            "leave.services.storage.signed_document_url",
            return_value="https://signed.example/doc.pdf",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.hr = User.objects.create_user(
            username="hr@documents.test",
            password="testpass123",
            first_name="Hana",
            role=User.Role.HR,
        )
        self.team = make_team("Alpha Team", ("supervisor", "hod"))
        self.other = make_team("Beta Team", ("supervisor", "hod"))

        # The manager of Alpha, and a member of it.
        self.manager = User.objects.create_user(
            username="manager@documents.test",
            password="testpass123",
            first_name="Mia",
            role=User.Role.EMPLOYEE,
        )
        role = ensure_roles("supervisor")["supervisor"]
        TeamRoleAssignment.objects.create(
            team=self.team, role=role, user=self.manager, is_team_manager=True
        )
        EmployeeProfile.objects.create(user=self.manager, team=self.team)

        self.member = self._employee("member@documents.test", self.team)
        self.other_member = self._employee("beta@documents.test", self.other)

        self.manager_app = _application(self.manager)
        self.member_app = _application(self.member)
        self.other_app = _application(self.other_member)

        self.manager_supporting = _supporting(self.manager_app, "manager.pdf")
        self.member_supporting = _supporting(self.member_app, "member.pdf")
        self.other_supporting = _supporting(self.other_app, "beta.pdf")

        self.manager_approved = _approved(self.manager_app, "manager-approved.pdf")
        self.member_approved = _approved(self.member_app, "member-approved.pdf")
        self.other_approved = _approved(self.other_app, "beta-approved.pdf")

    def _employee(self, username, team):
        user = User.objects.create_user(
            username=username, password="testpass123", role=User.Role.EMPLOYEE
        )
        EmployeeProfile.objects.create(user=user, team=team)
        return user

    def _get(self, url, user=None):
        if user is not None:
            self.client.force_authenticate(user)
        response = self.client.get(url)
        self.client.force_authenticate(None)
        return response

    def _supporting_ids(self, user):
        response = self._get(SUPPORTING_URL, user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["id"] for row in response.data}

    def _approved_ids(self, user):
        response = self._get(APPROVED_URL, user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["id"] for row in response.data}

    def test_employee_sees_only_their_own_documents(self):
        self.assertEqual(
            self._supporting_ids(self.member), {str(self.member_supporting.id)}
        )
        self.assertEqual(
            self._approved_ids(self.member), {str(self.member_approved.id)}
        )

    def test_manager_sees_their_team_and_themselves(self):
        self.assertEqual(
            self._supporting_ids(self.manager),
            {str(self.manager_supporting.id), str(self.member_supporting.id)},
        )
        self.assertEqual(
            self._approved_ids(self.manager),
            {str(self.manager_approved.id), str(self.member_approved.id)},
        )

    def test_manager_does_not_see_another_team(self):
        self.assertNotIn(str(self.other_supporting.id), self._supporting_ids(self.manager))
        self.assertNotIn(str(self.other_approved.id), self._approved_ids(self.manager))

    def test_hr_sees_the_whole_institution(self):
        self.assertEqual(
            self._supporting_ids(self.hr),
            {
                str(self.manager_supporting.id),
                str(self.member_supporting.id),
                str(self.other_supporting.id),
            },
        )
        self.assertEqual(
            self._approved_ids(self.hr),
            {
                str(self.manager_approved.id),
                str(self.member_approved.id),
                str(self.other_approved.id),
            },
        )

    def test_superuser_sees_the_whole_institution(self):
        superuser = User.objects.create_superuser(
            username="root@documents.test",
            password="testpass123",
            role=User.Role.EMPLOYEE,
        )
        self.assertEqual(len(self._supporting_ids(superuser)), 3)
        self.assertEqual(len(self._approved_ids(superuser)), 3)

    def test_unauthenticated_is_refused(self):
        self.assertEqual(
            self._get(SUPPORTING_URL).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self._get(APPROVED_URL).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_rows_carry_applicant_and_filing(self):
        response = self._get(APPROVED_URL, self.member)
        row = response.data[0]
        self.assertEqual(row["employee"]["id"], self.member.id)
        self.assertEqual(row["employee"]["full_name"], self.member.get_full_name())
        self.assertEqual(row["application"]["id"], str(self.member_app.id))
        self.assertTrue(row["available"])
        self.assertEqual(row["download_url"], "https://signed.example/doc.pdf")

    def test_retired_supporting_documents_are_hidden_unless_requested(self):
        retired = _supporting(
            self.member_app,
            "old.pdf",
            status=SupportingDocument.Status.RETIRED,
            retire_reason=SupportingDocument.RetireReason.REPLACED,
        )
        self.assertNotIn(str(retired.id), self._supporting_ids(self.member))

        response = self._get(f"{SUPPORTING_URL}?include_retired=true", self.member)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(str(retired.id), {row["id"] for row in response.data})
