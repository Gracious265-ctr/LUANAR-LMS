"""Unit 11 port: HR audit log + finalized-leave view over ``AuditEvent``."""

import uuid
from datetime import date, timedelta

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import LeaveDocumentTemplate
from documents.services import get_template
from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
    SupportingDocument,
)
from users.models import User

from workflows.models import Delegation, Reassignment, Workflow, WorkflowStage
from workflows.services import (
    cancel_delegation,
    approve_delegation,
    reject_delegation,
    reassign_application,
)

from .admin import AuditEventAdmin
from .models import AuditEvent
from .services import changed_fields, record_event, target_summary

SEED_PASSWORD = "testpass123"


def make_user(role: str, email: str) -> User:
    return User.objects.create_user(
        username=email,
        email=email,
        password=SEED_PASSWORD,
        first_name="Test",
        last_name=role.capitalize(),
        role=role,
    )


def make_hr() -> User:
    return make_user(User.Role.HR, f"hr-{uuid.uuid4().hex[:6]}@audit.test")


def make_submitted_application(employee, *, approver=None) -> LeaveApplication:
    return LeaveApplication.objects.create(
        employee=employee,
        current_approver=approver,
        status=LeaveApplication.Status.SUBMITTED,
        reference_number=f"LUANAR-2026-{uuid.uuid4().hex[:5].upper()}",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 5),
        calculated_days=5,
        reason="Family visit",
        submitted_at=timezone.now(),
    )


def make_employee_profile(user: User):
    from users.models import EmployeeProfile

    return EmployeeProfile.objects.create(
        user=user,
        designation="Lecturer",
        department="Computer Science",
        category="academic",
        grade="D1",
    )


class AuditEventModelTests(TestCase):
    def test_str_and_ordering(self):
        hr = make_hr()
        application = make_submitted_application(make_user(User.Role.EMPLOYEE, "emp@t.test"))
        older = record_event(
            actor=hr,
            action="leave_application.submitted",
            target=application,
            prev_state="draft",
            new_state="submitted",
        )
        newer = record_event(
            actor=hr,
            action="leave_application.workflow_assigned",
            target=application,
            prev_state="submitted",
            new_state="pending",
        )
        self.assertIn("leave_application.submitted", str(older))
        self.assertEqual(list(AuditEvent.objects.all()), [newer, older])

    def test_record_event_targets_int_and_uuid_pks(self):
        hr = make_hr()
        employee = make_user("employee", "emp@audit.test")
        profile = make_employee_profile(employee)
        event = record_event(
            actor=hr,
            action="employee.created",
            target=profile,
            metadata={"summary": "Test Employee"},
        )
        refreshed = AuditEvent.objects.get(pk=event.pk)
        self.assertEqual(refreshed.object_id, str(profile.pk))
        self.assertIsNotNone(refreshed.content_object)
        self.assertEqual(refreshed.content_object, profile)


class AuditServiceTests(TestCase):
    def test_changed_fields_omits_unchanged(self):
        diff = changed_fields(
            {"name": "A", "days": 20, "active": True},
            {"name": "A", "days": 21, "active": True},
        )
        self.assertEqual(diff, {"before": {"days": 20}, "after": {"days": 21}})

    def test_changed_fields_limits_keys(self):
        diff = changed_fields(
            {"a": 1, "b": 2},
            {"a": 1, "b": 3},
            keys=["a"],
        )
        self.assertEqual(diff, {"before": {}, "after": {}})

    def test_changed_fields_jsonables_dates(self):
        diff = changed_fields(
            {"day": date(2026, 1, 1)},
            {"day": date(2026, 2, 2)},
        )
        self.assertEqual(
            diff,
            {"before": {"day": "2026-01-01"}, "after": {"day": "2026-02-02"}},
        )

    def test_target_summary_uses_reference_for_applications(self):
        application = make_submitted_application(
            make_user("employee", "emp@audit.test")
        )
        self.assertEqual(target_summary(application), application.reference_number)


class AuditEntryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = make_hr()
        self.employee = make_user("employee", "emp@audit.test")
        self.approver = make_user("supervisor", "sup@audit.test")
        self.application = make_submitted_application(
            self.employee, approver=self.approver
        )
        record_event(
            actor=self.hr,
            action="employee.created",
            target=make_employee_profile(self.employee),
            metadata={"summary": "Test Employee"},
        )
        record_event(
            actor=self.hr,
            action="leave_application.submitted",
            target=self.application,
            prev_state="draft",
            new_state="submitted",
        )

    def test_unauthenticated_is_401(self):
        response = self.client.get("/api/v1/audit-entries/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.get("/api/v1/finalized-leave/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_roles_are_403(self):
        self.client.force_authenticate(self.employee)
        for endpoint in ("/api/v1/audit-entries/", "/api/v1/finalized-leave/"):
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.approver)
        response = self.client.get("/api/v1/audit-entries/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resources_are_read_only(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post("/api/v1/audit-entries/", {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.post("/api/v1/finalized-leave/", {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_audit_entries_list_and_filters(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/v1/audit-entries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        actions = [entry["action"] for entry in results]
        self.assertEqual(
            actions,
            ["leave_application.submitted", "employee.created"],
        )
        self.assertEqual(results[0]["target_type"], "leaveapplication")
        self.assertEqual(results[0]["target_summary"], self.application.reference_number)

        response = self.client.get(
            "/api/v1/audit-entries/", {"action": "employee.created"}
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["actor_name"], self.hr.get_full_name())

        response = self.client.get(
            "/api/v1/audit-entries/", {"target_type": "employeeprofile"}
        )
        self.assertEqual(len(response.data["results"]), 1)

        response = self.client.get(
            "/api/v1/audit-entries/", {"actor": self.hr.pk}
        )
        self.assertEqual(len(response.data["results"]), 2)

    def test_audit_entry_retrieve(self):
        self.client.force_authenticate(self.hr)
        event = AuditEvent.objects.get(action="employee.created")
        response = self.client.get(f"/api/v1/audit-entries/{event.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], event.pk)


class FinalizedLeaveAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = make_hr()
        self.employee = make_user("employee", "emp@audit.test")
        self.other = make_user("employee", "other@audit.test")
        self.approver = make_user("supervisor", "sup@audit.test")
        self.app = make_submitted_application(self.employee, approver=self.approver)
        self.draft = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.DRAFT,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 3),
        )
        self.client.force_authenticate(self.hr)

    def test_lists_only_submitted_order_newest_first(self):
        later = make_submitted_application(self.other)
        later.submitted_at = self.app.submitted_at + timedelta(seconds=5)
        later.save(update_fields=["submitted_at"])
        response = self.client.get("/api/v1/finalized-leave/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(row["id"]) for row in response.data["results"]]
        self.assertEqual(ids, [str(later.pk), str(self.app.pk)])
        self.assertEqual(
            response.data["results"][0]["reference_number"], later.reference_number
        )

    def test_employee_search(self):
        response = self.client.get(
            "/api/v1/finalized-leave/", {"employee": self.employee.email}
        )
        self.assertEqual(
            [str(row["id"]) for row in response.data["results"]],
            [str(self.app.pk)],
        )
        response = self.client.get(
            "/api/v1/finalized-leave/", {"employee": self.other.email}
        )
        self.assertEqual(response.data["results"], [])

    def test_retrieve_draft_is_404(self):
        response = self.client.get(f"/api/v1/finalized-leave/{self.draft.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_returns_history_rollup(self):
        document = SupportingDocument.objects.create(
            application=self.app,
            file_path="docs/note.pdf",
            file_url="http://storage/note.pdf",
            file_name="note.pdf",
            file_size=100,
            content_type="application/pdf",
            status=SupportingDocument.Status.ACTIVE,
        )
        second_approver = make_user("hod", "hod2@audit.test")
        reassignment = reassign_application(
            application=self.app,
            to_approver=second_approver,
            actor=self.hr,
            reason="Coverage",
        )
        self.assertTrue(Reassignment.objects.filter(pk=reassignment.pk).exists())

        response = self.client.get(f"/api/v1/finalized-leave/{self.app.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.app.pk)
        self.assertEqual(len(response.data["documents"]), 1)
        self.assertEqual(response.data["documents"][0]["id"], str(document.pk))
        self.assertEqual(len(response.data["reassignments"]), 1)
        self.assertEqual(
            response.data["reassignments"][0]["to_approver"], second_approver.pk
        )
        audit_actions = [entry["action"] for entry in response.data["audit_entries"]]
        self.assertIn("application.reassigned", audit_actions)


class HRActionAuditWiringTests(TestCase):
    """Every HR configuration mutation writes one audit event."""

    def setUp(self):
        self.client = APIClient()
        self.hr = make_hr()
        self.client.force_authenticate(self.hr)
        self.employee = make_user("employee", "emp@audit.test")
        self.leave_type = LeaveType.objects.create(name="Annual", code="annual")
        self.leave_type_2 = LeaveType.objects.create(name="Sick", code="sick")
        make_employee_profile(self.employee)

    def _audit_events(self, action: str):
        return list(AuditEvent.objects.filter(action=action))

    def test_employee_create_and_update(self):
        response = self.client.post(
            "/api/v1/employees/",
            {
                "email": "jane@audit.test",
                "first_name": "Jane",
                "last_name": "Grey",
                "designation": "Lecturer",
                "department": "Chemistry",
                "category": "academic",
                "grade": "D2",
                "appointment_date": "2026-01-01",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("employee.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(
            created[0].metadata["summary"], "Jane Grey (Chemistry)"
        )
        self.assertIsNone(created[0].metadata.get("before"))
        self.assertEqual(created[0].metadata["after"]["department"], "Chemistry")

        profile_id = response.data["id"]
        response = self.client.patch(
            f"/api/v1/employees/{profile_id}/",
            {"department": "Physics"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("employee.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(
            updated[0].metadata["before"],
            {"department": "Chemistry"},
        )
        self.assertEqual(
            updated[0].metadata["after"],
            {"department": "Physics"},
        )

    def test_grade_entitlement_create_and_update(self):
        response = self.client.post(
            "/api/v1/entitlements/",
            {
                "grade_start": "D1",
                "grade_end": "D3",
                "days": 21,
                "effective_from": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("grade_entitlement.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["days"], 21)

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/entitlements/{pk}/", {"days": 24}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("grade_entitlement.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].metadata["before"], {"days": 21})
        self.assertEqual(updated[0].metadata["after"], {"days": 24})

    def test_leave_type_create_and_update(self):
        response = self.client.post(
            "/api/v1/leave-types/", {"name": "Maternity", "code": "mat"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("leave_type.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["name"], "Maternity")

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/leave-types/{pk}/", {"name": "Maternity Leave"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("leave_type.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].metadata["before"], {"name": "Maternity"})

    def test_leave_rule_create_and_update(self):
        response = self.client.post(
            "/api/v1/leave-rules/",
            {
                "leave_type": self.leave_type.pk,
                "max_duration_days": 30,
                "effective_from": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("leave_rule.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["max_duration_days"], 30)

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/leave-rules/{pk}/",
            {"max_duration_days": 25},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("leave_rule.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].metadata["before"], {"max_duration_days": 30})
        self.assertEqual(updated[0].metadata["after"], {"max_duration_days": 25})

    def test_financial_year_create_and_update(self):
        response = self.client.post(
            "/api/v1/financial-years/",
            {
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("financial_year.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["is_active"], True)

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/financial-years/{pk}/", {"is_active": False}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("financial_year.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].metadata["before"], {"is_active": True})
        self.assertEqual(updated[0].metadata["after"], {"is_active": False})

    def test_public_holiday_create_and_update(self):
        response = self.client.post(
            "/api/v1/public-holidays/",
            {"name": "Independence Day", "date": "2026-07-06"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("public_holiday.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["name"], "Independence Day")

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/public-holidays/{pk}/", {"name": "Independence"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("public_holiday.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].metadata["before"], {"name": "Independence Day"})

    def test_workflow_create_and_update(self):
        response = self.client.post(
            "/api/v1/workflows/",
            {
                "name": "Academic Approval",
                "employee_category": "academic",
                "department": "",
                "stages": [{"order": 1, "approver_role": "hod"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self._audit_events("workflow.created")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].metadata["after"]["name"], "Academic Approval")
        self.assertEqual(created[0].metadata["after"]["stages"], ["hod"])
        self.assertEqual(created[0].metadata["after"]["state"], "draft")

        pk = response.data["id"]
        response = self.client.patch(
            f"/api/v1/workflows/{pk}/",
            {
                "name": "Academic Approval v2",
                "employee_category": "academic",
                "department": "",
                "stages": [{"order": 1, "approver_role": "dean"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("workflow.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(
            updated[0].metadata["before"]["stages"], ["hod"]
        )
        self.assertEqual(
            updated[0].metadata["after"]["stages"], ["dean"]
        )

    def test_delegation_decision_actions(self):
        approver = make_user(User.Role.HOD, "hod@audit.test")
        delegate = make_user(User.Role.REGISTRAR, "reg@audit.test")
        delegation = Delegation.objects.create(
            approver=approver,
            delegate=None,
            requested_by=approver,
            request_reason="On leave",
            starts_on=timezone.localdate() - timedelta(days=1),
        )
        approve_delegation(
            delegation, self.hr, {"delegate": delegate, "decision_reason": "Confirmed"}
        )
        approved = self._audit_events("delegation.approved")
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].prev_state, "requested")
        self.assertEqual(approved[0].new_state, "approved")
        self.assertEqual(approved[0].metadata["reason"], "Confirmed")
        self.assertEqual(approved[0].metadata["after"]["delegate"], delegate.get_full_name())

        reject_approver = make_user(User.Role.HOD, "hod-reject@audit.test")
        request = Delegation.objects.create(
            approver=reject_approver,
            delegate=None,
            requested_by=reject_approver,
            request_reason="Second request",
            starts_on=timezone.localdate() - timedelta(days=1),
        )
        reject_delegation(request, self.hr, {"decision_reason": "No capacity"})
        rejected = self._audit_events("delegation.rejected")
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].metadata["reason"], "No capacity")

        cancel_approver = make_user(User.Role.HOD, "hod-cancel@audit.test")
        request = Delegation.objects.create(
            approver=cancel_approver,
            delegate=None,
            requested_by=cancel_approver,
            request_reason="Third request",
            starts_on=timezone.localdate() - timedelta(days=1),
        )
        approve_delegation(
            request, self.hr, {"delegate": delegate, "decision_reason": "Confirmed"}
        )
        cancel_delegation(request, self.hr, {"decision_reason": "Back now"})
        cancelled = self._audit_events("delegation.cancelled")
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(cancelled[0].prev_state, "approved")
        self.assertEqual(cancelled[0].new_state, "cancelled")

    def test_failed_delegation_action_writes_no_audit(self):
        approver = make_user(User.Role.HOD, "hod@audit.test")
        delegation = Delegation.objects.create(
            approver=approver,
            delegate=None,
            requested_by=approver,
            request_reason="On leave",
            starts_on=timezone.localdate() - timedelta(days=1),
        )
        approve_delegation(
            delegation, self.hr, {"delegate": make_user(User.Role.REGISTRAR, "reg2@audit.test"), "decision_reason": "Ok"}
        )
        with self.assertRaises(Exception):
            approve_delegation(
                delegation, self.hr, {"decision_reason": "Twice"}
            )
        self.assertEqual(AuditEvent.objects.filter(action="delegation.approved").count(), 1)

    def test_document_template_patch_audited(self):
        get_template()
        template = LeaveDocumentTemplate.objects.get()
        response = self.client.patch(
            "/api/v1/leave-document-template/",
            {"title": "LUANAR Leave Letter"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._audit_events("document_template.updated")
        self.assertEqual(len(updated), 1)
        self.assertEqual(
            updated[0].metadata["before"]["title"], template.title
        )
        self.assertEqual(
            updated[0].metadata["after"]["title"], "LUANAR Leave Letter"
        )


class AuditAdminTests(TestCase):
    def test_read_only_permissions(self):
        hr = make_hr()
        employee = make_user("employee", "emp@audit.test")
        application = make_submitted_application(employee)
        event = record_event(
            actor=hr,
            action="leave_application.submitted",
            target=application,
        )
        site = AdminSite()
        factory = RequestFactory()
        request = factory.get("/admin/")
        model_admin = AuditEventAdmin(AuditEvent, site)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, obj=event))
        self.assertFalse(model_admin.has_change_permission(request, obj=event))