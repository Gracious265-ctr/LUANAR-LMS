<<<<<<< HEAD
"""Unit 11 port: HR audit log + finalized-leave view over ``AuditEvent``."""

import uuid
from datetime import date, timedelta

from django.contrib.admin.sites import AdminSite
=======
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.db.models import Count
>>>>>>> feature/plans-teams
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

<<<<<<< HEAD
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
=======
from workflows.models import Delegation, Reassignment, Workflow
from workflows.testing import ensure_roles, make_approver, team_for

from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    register_chain_approvers,
)

from .admin import AuditEntryAdmin
from .models import AuditEntry, AuditEntryLockedError
from .serializers import AuditedModelSerializer
from .services import changed_fields, record_audit
>>>>>>> feature/plans-teams

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


<<<<<<< HEAD
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
=======
class AuditEntryModelTests(TestCase):
    """AuditEntry shape, ordering, and JSON-safe detail storage."""

    def test_target_type_codes_are_registered_choices(self):
        used = {
            cls.target_type
            for cls in AuditedModelSerializer.__subclasses__()
            if cls.__dict__.get("target_type") is not None
        }
        missing = used - set(AuditEntry.TargetType.values)
        self.assertEqual(missing, set())

    def test_str_reports_action_and_target(self):
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type="leavetype",
            target_id=7,
            target_summary="Annual leave",
        )
        self.assertEqual(str(entry), "Created leavetype 7")
        self.assertIsNotNone(entry.created_at)

    def test_ordering_is_newest_first(self):
        actor = make_hr()
        first = record_audit(
            actor=actor, action=AuditEntry.Action.CREATED,
            target_type="leavetype", target_id=1, target_summary="A",
        )
        second = record_audit(
            actor=actor, action=AuditEntry.Action.UPDATED,
            target_type="leavetype", target_id=2, target_summary="B",
        )
        self.assertEqual([entry.pk for entry in AuditEntry.objects.all()], [second.pk, first.pk])

    def test_detail_normalizes_dates_for_json(self):
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type="leaverule",
            target_id=3,
            target_summary="Annual rule",
            detail={
                "before": {"effective_from": date(2026, 1, 1)},
                "after": {"effective_from": date(2026, 2, 1)},
            },
        )
        entry.refresh_from_db()
        self.assertEqual(entry.detail["before"]["effective_from"], "2026-01-01")

    def test_detail_encodes_decimals_as_strings(self):
        """A restored day count is a Decimal; json.dumps refuses it outright."""
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.BALANCE_RESTORED,
            target_type="cancellation",
            target_id=1,
            target_summary="Approved leave",
            detail={"days": Decimal("5.0"), "nested": [Decimal("1.5")]},
        )
        entry.refresh_from_db()
        self.assertEqual(entry.detail["days"], "5.0")
        self.assertEqual(entry.detail["nested"], ["1.5"])

    def test_detail_survives_a_value_it_cannot_encode(self):
        """An audit write shares a transaction with the business write.

        An entry that raises rolls the business write back with it, so an
        unconvertible value is stringified rather than raised on: a value nobody
        thought to convert is not worth losing an approval over.
        """
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type="leaverule",
            target_id=3,
            target_summary="Annual rule",
            detail={"after": {"count": Count("id")}},
        )
        entry.refresh_from_db()
        self.assertIsInstance(entry.detail["after"]["count"], str)
        self.assertTrue(entry.detail["after"]["count"])

    def test_detail_encodes_non_finite_floats_as_strings(self):
        """json.dumps emits ``NaN``; PostgreSQL's jsonb then rejects it."""
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type="leaverule",
            target_id=3,
            target_summary="Annual rule",
            detail={"before": {"ratio": float("inf")}},
        )
        entry.refresh_from_db()
        self.assertEqual(entry.detail["before"]["ratio"], "inf")


class AuditServiceTests(TestCase):
    """record_audit and changed_fields behavior."""

    def test_record_audit_persists_all_fields(self):
        actor = make_hr()
        entry = record_audit(
            actor=actor,
            action=AuditEntry.Action.APPROVED,
            target_type="delegation",
            target_id=9,
            target_summary="Delegation: Dean → HOD",
            detail={"before": {"status": "requested"}, "after": {"status": "approved"}},
            reason="Covering absence",
        )
        stored = AuditEntry.objects.get(pk=entry.pk)
        self.assertEqual(stored.actor, actor)
        self.assertEqual(stored.action, "approved")
        self.assertEqual(stored.target_type, "delegation")
        self.assertEqual(stored.target_id, "9")
        self.assertEqual(stored.reason, "Covering absence")
        self.assertEqual(stored.detail["after"], {"status": "approved"})

    def test_record_audit_trims_summary_and_reason(self):
        actor = make_hr()
        entry = record_audit(
            actor=actor, action=AuditEntry.Action.CREATED,
            target_type="employee", target_id=1,
            target_summary="  Jane Dean  ", reason="  ",
        )
        self.assertEqual(entry.target_summary, "Jane Dean")
        self.assertEqual(entry.reason, "")

    def test_changed_fields_drops_unchanged(self):
        result = changed_fields(
            {"days": 20, "grade_start": "A"},
            {"days": 21, "grade_start": "A"},
        )
        self.assertEqual(
            result, {"before": {"days": 20}, "after": {"days": 21}}
        )

    def test_changed_fields_respects_limited_keys(self):
        result = changed_fields(
            {"days": 20, "grade_start": "A"},
            {"days": 21, "grade_start": "B"},
            keys=["days"],
        )
        self.assertEqual(result, {"before": {"days": 20}, "after": {"days": 21}})


class AuditEntryApiTests(TestCase):
    """Authentication, authorization, filtering, and retrieval of the log."""

    def setUp(self):
        self.client = APIClient()
        self.hr_user = make_hr()
        self.employee_user = make_user(User.Role.EMPLOYEE, "emp-1@audit.test")
        self.approver_user = make_approver("hod", username="hod-1@audit.test")

        self.entry = record_audit(
            actor=self.hr_user,
            action=AuditEntry.Action.UPDATED,
            target_type="entitlement",
            target_id=5,
            target_summary="Annual leave: A–C, 21 days (from 2026-01-01)",
            detail={"before": {"days": 20}, "after": {"days": 21}},
        )
        self.list_url = "/api/v1/audit-entries/"
        self.detail_url = f"/api/v1/audit-entries/{self.entry.pk}/"

    def test_list_and_retrieve_require_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_roles_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.approver_user)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_read_only_resource_rejects_writes(self):
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(
            self.client.post(self.list_url, {}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )
        self.assertEqual(
            self.client.delete(self.detail_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_hr_can_list_entries_newest_first(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["actor"], self.hr_user.pk)
        self.assertEqual(row["actor_name"], self.hr_user.get_full_name())
        self.assertEqual(row["action"], "updated")
        self.assertEqual(row["target_type"], "entitlement")
        self.assertEqual(row["target_id"], "5")
        self.assertEqual(row["detail"]["before"], {"days": 20})
        self.assertEqual(row["detail"]["after"], {"days": 21})

    def test_hr_can_retrieve_entry(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.entry.pk)

    def test_filters_action_target_type_target_id_actor(self):
        employee = make_user(User.Role.EMPLOYEE, "emp-2@audit.test")
        record_audit(
            actor=employee, action=AuditEntry.Action.SUBMITTED,
            target_type="application", target_id="42", target_summary="LUANAR-2026-00002",
        )
        self.client.force_authenticate(user=self.hr_user)

        def ids(query):
            return self.client.get(self.list_url, query).data["results"]

        self.assertEqual([r["target_id"] for r in ids({"action": "updated"})], ["5"])
        self.assertEqual([r["target_id"] for r in ids({"target_type": "application"})], ["42"])
        self.assertEqual([r["target_id"] for r in ids({"target_id": "42"})], ["42"])
        self.assertEqual([r["target_id"] for r in ids({"actor": employee.pk})], ["42"])
        self.assertEqual(ids({"target_id": "999"}), [])

    def test_invalid_actor_filter_returns_400_not_500(self):
        self.client.force_authenticate(user=self.hr_user)
        for bad in ("abc", "-1", "4.5"):
            response = self.client.get(self.list_url, {"actor": bad})
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, f"actor={bad}"
            )

    def test_valid_actor_filter_still_works(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url, {"actor": self.hr_user.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class FinalizedLeaveApiTests(TestCase):
    """Organization-wide submitted-application reads with history roll-up."""

    def setUp(self):
        self.client = APIClient()
        self.hr_user = make_hr()
        self.employee_user = make_user(User.Role.EMPLOYEE, "emp-fin@audit.test")
        self.other_employee = make_user(User.Role.EMPLOYEE, "emp-fin2@audit.test")

        self.app = make_submitted_application(self.employee_user)
        self.draft = LeaveApplication.objects.create(
            employee=self.other_employee, reason="Unfinished works"
        )
        self.list_url = "/api/v1/finalized-leave/"
        self.detail_url = f"/api/v1/finalized-leave/{self.app.id}/"
        self.draft_url = f"/api/v1/finalized-leave/{self.draft.id}/"

    def test_list_and_retrieve_require_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_only_submitted_applications_are_listed(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["reference_number"], self.app.reference_number)
        self.assertEqual(row["employee_name"], self.employee_user.get_full_name())
        self.assertEqual(row["calculated_days"], 5)

    def test_approved_applications_are_visible_to_hr(self):
        """Unit 25 D6: an approved application is the finalized record.

        The view used to filter ``SUBMITTED`` only, so HR could not see (nor
        retrieve) any application that had actually reached its final approval.
        """
        self.app.status = LeaveApplication.Status.APPROVED
        self.app.save(update_fields=["status"])
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["reference_number"], self.app.reference_number
        )
        detail = self.client.get(self.detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["reference_number"], self.app.reference_number)

    def test_rejected_and_cancelled_applications_stay_hidden(self):
        """Unit 25 D6: only in-flight and approved; the audit log covers the rest."""
        rejected = make_submitted_application(self.employee_user)
        rejected.status = LeaveApplication.Status.REJECTED
        rejected.save(update_fields=["status"])
        cancelled = make_submitted_application(self.employee_user)
        cancelled.status = LeaveApplication.Status.CANCELLED
        cancelled.save(update_fields=["status"])
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["reference_number"], self.app.reference_number
        )
        for hidden in (rejected, cancelled):
            self.assertEqual(
                self.client.get(
                    f"/api/v1/finalized-leave/{hidden.id}/"
                ).status_code,
                status.HTTP_404_NOT_FOUND,
            )

    def test_list_ordered_by_submitted_at_newest_first(self):
        self.client.force_authenticate(user=self.hr_user)
        latest = make_submitted_application(self.other_employee)
        LeaveApplication.objects.filter(pk=latest.pk).update(
            submitted_at=timezone.now() - timedelta(days=3)
        )
        self.app.submitted_at = timezone.now()
        self.app.save(update_fields=["submitted_at"])
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.app.id, latest.id])

    def test_list_rows_omit_history_rollup(self):
        self.client.force_authenticate(user=self.hr_user)
        row = self.client.get(self.list_url).data["results"][0]
        self.assertNotIn("documents", row)
        self.assertNotIn("reassignments", row)
        self.assertNotIn("audit_entries", row)

    def test_list_resolves_leave_type_name(self):
        leave_type = LeaveType.objects.create(name="Annual leave", code="annual")
        LeaveApplication.objects.filter(pk=self.app.pk).update(
            leave_type_id=leave_type.pk
        )
        self.client.force_authenticate(user=self.hr_user)
        row = self.client.get(self.list_url).data["results"][0]
        self.assertEqual(row["leave_type_name"], "Annual leave")

    def test_employee_search_icontains(self):
        self.client.force_authenticate(user=self.hr_user)
        make_submitted_application(self.other_employee)
        response = self.client.get(self.list_url, {"employee": self.employee_user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.app.id)

    def test_draft_id_returns_404(self):
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(self.client.get(self.draft_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_rolls_up_documents_reassignments_and_audit(self):
        self.client.force_authenticate(user=self.hr_user)
        SupportingDocument.objects.create(
            application=self.app,
            file_path="files/app.pdf",
            file_url="https://storage.test/app.pdf",
            file_name="app.pdf",
            file_size=1024,
            content_type="application/pdf",
        )
        to_approver = make_approver("dean", username="dean-fin@audit.test")
        from_approver = make_approver("hod", username="hod-fin@audit.test")
        Reassignment.objects.create(
            application=self.app,
            from_approver=from_approver,
            to_approver=to_approver,
            reason="Covering",
            decided_by=self.hr_user,
        )
        newer = record_audit(
            actor=self.hr_user, action=AuditEntry.Action.REASSIGNED,
            target_type="reassignment", target_id="1",
            target_summary=f"Reassignment of {self.app.reference_number}", reason="Covering",
        )
        submitted = record_audit(
            actor=self.employee_user, action=AuditEntry.Action.SUBMITTED,
            target_type="application", target_id=self.app.id,
            target_summary=self.app.reference_number,
        )
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data
        self.assertEqual(payload["reference_number"], self.app.reference_number)
        self.assertEqual(len(payload["documents"]), 1)
        self.assertEqual(payload["documents"][0]["file_name"], "app.pdf")
        self.assertEqual(len(payload["reassignments"]), 1)
        self.assertEqual(payload["reassignments"][0]["to_approver"], to_approver.pk)
        submissions = [entry["id"] for entry in payload["audit_entries"]]
        self.assertEqual(submissions, [submitted.pk])
        self.assertNotIn(newer.pk, submissions)
        self.assertEqual(payload["audit_entries"][0]["id"], submitted.pk)


class AuditWiringTests(StubProviderMixin, TestCase):
    """Each audited action produces the expected audit entry."""

    def setUp(self):
        self.stub = self.use_stub()
        self.client = APIClient()
        self.hr_user = make_hr()
        self.client.force_authenticate(user=self.hr_user)
        self.today = timezone.localdate()
        # Roles are HR data, not migration seed: a bare test database has none.
        ensure_roles("supervisor", "hod", "dean", "registrar", "dvc")
        self.team = team_for("Bunda College Team")

    def _entry_for(self, target_type, target_id):
        return AuditEntry.objects.filter(
            target_type=target_type, target_id=str(target_id)
        ).first()

    def test_employee_create_and_update_are_audited(self):
        response = self.client.post(
            "/api/v1/employees/",
            {
                "email": "staff-new@audit.test",
                "first_name": "New",
                "last_name": "Staff",
                "password": "initial-pass-123",
                "designation": "Lecturer",
                # An existing team's id, not a typed name: approver eligibility is
                # decided by comparing team references, so a free-text team name
                # could not be compared to anything.
                "team": self.team.id,
                "category": "academic",
                "grade": "C",
                "appointment_date": "2023-05-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        employee_id = response.data["id"]
        created = self._entry_for("employee", employee_id)
        self.assertIsNotNone(created)
        self.assertEqual(created.action, "created")
        self.assertEqual(created.actor, self.hr_user)
        self.assertIsNone(created.detail["before"])

        response = self.client.patch(
            f"/api/v1/employees/{employee_id}/",
            {"designation": "Senior Lecturer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = AuditEntry.objects.filter(
            target_type="employee", target_id=str(employee_id), action="updated"
        ).first()
        self.assertIsNotNone(updated)
        self.assertEqual(updated.detail["before"]["designation"], "Lecturer")
        self.assertEqual(updated.detail["after"]["designation"], "Senior Lecturer")

    def test_entitlement_create_and_update_are_audited(self):
        response = self.client.post(
            "/api/v1/entitlements/",
            {
                "grade_start": "A",
                "grade_end": "B",
                "days": 20,
                "effective_from": self.today.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry_id = response.data["id"]
        self.assertEqual(self._entry_for("entitlement", entry_id).action, "created")

        response = self.client.patch(
            f"/api/v1/entitlements/{entry_id}/", {"days": 22}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._entry_for("entitlement", entry_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.detail["before"]["days"], 20)
        self.assertEqual(updated.detail["after"]["days"], 22)

    def test_leave_type_create_and_update_are_audited(self):
        response = self.client.post(
            "/api/v1/leave-types/", {"name": "Compassionate leave"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry_id = response.data["id"]
        self.assertEqual(self._entry_for("leavetype", entry_id).action, "created")

        response = self.client.patch(
            f"/api/v1/leave-types/{entry_id}/",
            {"name": "Compassionate leave (revised)"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._entry_for("leavetype", entry_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.detail["before"]["name"], "Compassionate leave")

    def test_leave_rule_create_and_update_are_audited(self):
        leave_type = LeaveType.objects.create(name="Annual leave", code="annual")
        response = self.client.post(
            "/api/v1/leave-rules/",
            {
                "leave_type": leave_type.pk,
                "max_duration_days": 30,
                "eligibility": "All staff",
                "min_notice_days": 1,
                "requires_supporting_document": False,
                "consumes_annual_entitlement": True,
                "effective_from": (self.today - timedelta(days=10)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule_id = response.data["id"]
        self.assertEqual(self._entry_for("leaverule", rule_id).action, "created")

        response = self.client.patch(
            f"/api/v1/leave-rules/{rule_id}/", {"max_duration_days": 32}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._entry_for("leaverule", rule_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.detail["before"]["max_duration_days"], 30)
        self.assertEqual(updated.detail["after"]["max_duration_days"], 32)

    def test_financial_year_create_and_update_are_audited(self):
        response = self.client.post(
            "/api/v1/financial-years/",
            {
                "start_date": date(2026, 7, 1).isoformat(),
                "end_date": date(2027, 6, 30).isoformat(),
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        fy_id = response.data["id"]
        self.assertEqual(self._entry_for("financialyear", fy_id).action, "created")

        response = self.client.patch(
            f"/api/v1/financial-years/{fy_id}/", {"is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._entry_for("financialyear", fy_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.detail["before"]["is_active"], True)
        self.assertEqual(updated.detail["after"]["is_active"], False)

    def test_public_holiday_create_and_update_are_audited(self):
        response = self.client.post(
            "/api/v1/public-holidays/",
            {"name": "Independence Day", "date": date(2026, 7, 6).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        holiday_id = response.data["id"]
        self.assertEqual(self._entry_for("publicholiday", holiday_id).action, "created")

        response = self.client.patch(
            f"/api/v1/public-holidays/{holiday_id}/",
            {"name": "Independence Day (public)"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = self._entry_for("publicholiday", holiday_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.detail["before"]["name"], "Independence Day")

    def test_a_team_and_its_chain_are_audited_on_creation(self):
        """A chain is created with a team, so both are recorded together.

        The two entries are what let somebody read back, years later, that a
        step came into being as part of a team rather than as a change to
        something that already existed.
        """
        response = self.client.post(
            "/api/v1/teams/",
            {
                "name": "Registry team",
                "new_workflow": {
                    "name": "Registry approval",
                    "sections": [
                        {"name": "Supervisor", "approver_role": "supervisor"},
                        {"name": "HOD", "approver_role": "hod"},
                    ],
                },
>>>>>>> feature/plans-teams
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
<<<<<<< HEAD
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
=======
        workflow_id = response.data["workflow"]
        created = self._entry_for("workflow", workflow_id)
        self.assertEqual(created.action, "created")
        self.assertEqual(
            [
                s["approver_role"]
                for s in created.detail["after"]["workflow"]["sections"]
            ],
            ["supervisor", "hod"],
        )
        self.assertEqual(
            created.detail["after"]["created_with_team"], "Registry team"
        )

    def test_a_chains_steps_are_audited_when_the_team_is_saved(self):
        """Steps change as a consequence of saving a team, and that is recorded.

        A chain has no edit of its own, so the "before" and "after" of its steps
        are the record of what the team's form changed — which is why the entry
        names the team.
        """
        response = self.client.post(
            "/api/v1/teams/",
            {
                "name": "Registry team",
                "new_workflow": {
                    "name": "Registry approval",
                    "sections": [
                        {"name": "Supervisor", "approver_role": "supervisor"},
                        {"name": "HOD", "approver_role": "hod"},
                    ],
                },
            },
            format="json",
        )
        workflow_id = response.data["workflow"]
        self.client.patch(
            f"/api/v1/teams/{response.data['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {"name": "Registrar", "approver_role": "registrar"},
                        {"name": "DVC", "approver_role": "dvc"},
                    ]
                }
            },
            format="json",
        )
        updated = self._entry_for("workflow", workflow_id)
        self.assertEqual(updated.action, "updated")
        self.assertEqual(
            [s["approver_role"] for s in updated.detail["before"]["sections"]],
            ["supervisor", "hod"],
        )
        self.assertEqual(
            [s["approver_role"] for s in updated.detail["after"]["sections"]],
            ["registrar", "dvc"],
        )
        self.assertEqual(updated.detail["team"], "Registry team")

    def _create_delegation(self, approver, delegate=None, ends_on=None):
        payload = {
            "approver": approver.pk,
            "starts_on": self.today.isoformat(),
            "ends_on": ends_on,
        }
        if delegate is not None:
            payload["delegate"] = delegate.pk
        response = self.client.post("/api/v1/delegations/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["id"]

    def test_delegation_approve_reject_cancel_are_audited(self):
        dean = make_approver("dean", username="dean-audit@audit.test")
        dean2 = make_approver("dean", username="dean-audit2@audit.test")
        dean3 = make_approver("dean", username="dean-audit3@audit.test")
        hod = make_approver("hod", username="hod-audit@audit.test")
        hod2 = make_approver("hod", username="hod-audit2@audit.test")

        delegation_id = self._create_delegation(dean, hod)
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {
                "decision_reason": "Dean is away",
                "delegate": hod.pk,
>>>>>>> feature/plans-teams
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
<<<<<<< HEAD
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
=======
        approved = self._entry_for("delegation", delegation_id)
        self.assertEqual(approved.action, "approved")
        self.assertEqual(approved.actor, self.hr_user)
        self.assertEqual(approved.reason, "Dean is away")
        self.assertEqual(approved.detail["before"]["status"], "requested")
        self.assertEqual(approved.detail["after"]["status"], "approved")
        self.assertEqual(approved.detail["after"]["delegate_id"], hod.pk)

        second = self._create_delegation(dean2, hod)
        response = self.client.post(
            f"/api/v1/delegations/{second}/reject/",
            {"decision_reason": "Duplicate request"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rejected = self._entry_for("delegation", second)
        self.assertEqual(rejected.action, "rejected")
        self.assertEqual(rejected.detail["after"]["status"], "rejected")

        third = self._create_delegation(dean3, hod2)
        response = self.client.post(
            f"/api/v1/delegations/{third}/approve/",
            {"decision_reason": "Cover", "delegate": hod2.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(
            f"/api/v1/delegations/{third}/cancel/",
            {"decision_reason": "No longer needed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cancelled = self._entry_for("delegation", third)
        self.assertEqual(cancelled.action, "cancelled")
        self.assertEqual(cancelled.detail["after"]["status"], "cancelled")
        self.assertEqual(cancelled.reason, "No longer needed")

    def test_failed_delegation_action_writes_no_audit_entry(self):
        dean = make_approver("dean", username="dean-audit2@audit.test")
        hod = make_approver("hod", username="hod-audit2@audit.test")
        delegation_id = self._create_delegation(dean, hod)
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"decision_reason": "", "delegate": hod.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # The request itself is audited on create; the *decision* must not be.
        actions = set(
            AuditEntry.objects.filter(target_type="delegation").values_list(
                "action", flat=True
            )
        )
        self.assertEqual(actions, {"created"})

    def test_delegation_create_is_audited(self):
        dean = make_approver("dean", username="dean-audit3@audit.test")
        hod = make_approver("hod", username="hod-audit3@audit.test")
        delegation_id = self._create_delegation(dean, hod)

        created = self._entry_for("delegation", delegation_id)
        self.assertEqual(created.action, "created")
        # HR created this on the dean's behalf, so HR is the actor.
        self.assertEqual(created.actor, self.hr_user)
        self.assertEqual(created.detail["after"]["status"], "requested")
        self.assertEqual(created.detail["after"]["delegate_id"], hod.pk)

    def test_reassignment_is_audited(self):
        employee = make_user(User.Role.EMPLOYEE, "emp-re-assign@audit.test")
        app = make_submitted_application(employee)
        to_approver = make_approver("hod", username="hod-re-assign@audit.test")
        response = self.client.post(
            "/api/v1/reassignments/",
            {
                "application": app.id,
                "to_approver": to_approver.pk,
                "reason": "Original approver unavailable",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reassignment_id = response.data["id"]
        entry = AuditEntry.objects.get(
            action=AuditEntry.Action.REASSIGNED,
            target_type="reassignment",
            target_id=str(reassignment_id),
        )
        self.assertEqual(entry.actor, self.hr_user)
        self.assertEqual(entry.reason, "Original approver unavailable")
        self.assertEqual(entry.detail["before"]["current_approver_id"], None)
        self.assertEqual(entry.detail["after"]["current_approver_id"], to_approver.pk)

    def test_template_patch_is_audited(self):
        response = self.client.patch(
            "/api/v1/leave-document-template/",
            {"intro": "This is the official opening."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        template = get_template()
        entry = AuditEntry.objects.get(
            target_type="document-template", target_id=str(template.pk)
        )
        self.assertEqual(entry.action, "updated")
        self.assertEqual(entry.actor, self.hr_user)
        self.assertEqual(entry.target_summary, template.title)
        self.assertNotIn("title", entry.detail["before"])
        self.assertEqual(
            entry.detail["after"]["intro"], "This is the official opening."
        )

    def test_submit_is_audited_with_reference_number(self):
        employee = make_user(User.Role.EMPLOYEE, "emp-submit@audit.test")
        self.stub.register_employee(employee)
        register_chain_approvers(self.stub)
        self.client.force_authenticate(user=employee)
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Family visit",
        )
        response = self.client.post(f"/api/v1/leave-applications/{app.id}/submit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = AuditEntry.objects.get(
            target_type="application",
            target_id=str(app.id),
            action=AuditEntry.Action.SUBMITTED,
        )
        self.assertEqual(entry.actor, employee)
        self.assertEqual(entry.target_summary, response.data["reference_number"])
        self.assertEqual(entry.detail["before"]["status"], "draft")
        self.assertEqual(entry.detail["after"]["status"], "submitted")


class AuditEntryAdminTests(TestCase):
    """Audit admin is a view-only inspector."""

    def setUp(self):
        self.site = AdminSite()

    def test_registered_and_has_no_delete_permission(self):
        admin = AuditEntryAdmin(AuditEntry, self.site)
        self.assertFalse(admin.has_delete_permission(None))

    def test_changeform_renders(self):
        hr = make_hr()
        entry = record_audit(
            actor=hr, action=AuditEntry.Action.CREATED,
            target_type="leavetype", target_id=3, target_summary="Annual leave",
        )
        request = RequestFactory().get(f"/admin/audit/auditentry/{entry.pk}/change/")
        hr.is_staff = True
        hr.is_superuser = True
        hr.save(update_fields=["is_staff", "is_superuser"])
        request.user = hr
        admin = AuditEntryAdmin(AuditEntry, self.site)
        response = admin.changeform_view(request, object_id=str(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class AuditedModelSerializerAtomicityTests(TestCase):
    """A failed audit write rolls back the audited create/update."""

    def setUp(self):
        self.actor = make_hr()

    def _serializer_class(self):
        class _AuditedLeaveTypeSerializer(AuditedModelSerializer):
            target_type = "leavetype"
            audit_fields = ["name", "code"]

            class Meta:
                model = LeaveType
                fields = ["id", "name", "code"]

        return _AuditedLeaveTypeSerializer

    def _serializer(self, *args, **kwargs):
        from rest_framework.test import APIRequestFactory

        request = APIRequestFactory().post("/")
        request.user = self.actor
        return self._serializer_class()(*args, context={"request": request}, **kwargs)

    def test_create_rolls_back_when_audit_fails(self):
        serializer = self._serializer(
            data={"name": "Study leave", "code": "study"}
        )
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "audit.serializers.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        self.assertFalse(LeaveType.objects.filter(code="study").exists())

    def test_update_rolls_back_when_audit_fails(self):
        leave_type = LeaveType.objects.create(name="Annual leave", code="annual")
        serializer = self._serializer(
            leave_type, data={"name": "Renamed leave", "code": "annual"}
        )
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "audit.serializers.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        leave_type.refresh_from_db()
        self.assertEqual(leave_type.name, "Annual leave")


class AuditEntryIntegrityTests(TestCase):
    """The append-only log protects its actor rows and refuses mutation."""

    def _entry(self):
        actor = make_user(User.Role.HR, "immutable-log@audit.test")
        return record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type="leavetype",
            target_id="1",
            target_summary="Annual leave",
        )

    def test_actor_deletion_is_protected(self):
        from django.db.models.deletion import ProtectedError

        actor = make_user(User.Role.HR, "protect-log@audit.test")
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type="leavetype",
            target_id="1",
            target_summary="Annual leave",
        )
        with self.assertRaises(ProtectedError):
            actor.delete()
        self.assertTrue(
            User.objects.filter(email="protect-log@audit.test").exists()
        )
        self.assertEqual(AuditEntry.objects.count(), 1)

    def test_instance_update_is_rejected(self):
        entry = self._entry()
        entry.reason = "rewritten"
        with self.assertRaises(AuditEntryLockedError):
            entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.reason, "")

    def test_instance_delete_is_rejected(self):
        entry = self._entry()
        with self.assertRaises(AuditEntryLockedError):
            entry.delete()
        self.assertTrue(AuditEntry.objects.filter(pk=entry.pk).exists())

    def test_queryset_update_is_rejected(self):
        entry = self._entry()
        with self.assertRaises(AuditEntryLockedError):
            AuditEntry.objects.filter(pk=entry.pk).update(reason="rewritten")
        entry.refresh_from_db()
        self.assertEqual(entry.reason, "")

    def test_queryset_delete_is_rejected(self):
        entry = self._entry()
        with self.assertRaises(AuditEntryLockedError):
            AuditEntry.objects.filter(pk=entry.pk).delete()
        self.assertTrue(AuditEntry.objects.filter(pk=entry.pk).exists())

    def test_bulk_delete_of_every_entry_is_rejected(self):
        self._entry()
        with self.assertRaises(AuditEntryLockedError):
            AuditEntry.objects.all().delete()
        self.assertEqual(AuditEntry.objects.count(), 1)
>>>>>>> feature/plans-teams
