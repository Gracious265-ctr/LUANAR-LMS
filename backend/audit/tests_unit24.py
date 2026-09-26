"""Unit 24 tests: audit completeness, immutable trail, admin recorder, timeline.

Covers the ORM-level append-only guarantee for ``AuditEvent``, the
``AuditedModelAdmin`` recorder for HR-config edits made through the Django
admin, the draft-document removal regression (event must keep its
``object_id``), the per-application/server timeline endpoint (shape, ordering,
access rules, related-target inclusion, delegation exclusion), and the
historical-integrity guarantee that HR-config edits never mutate a submitted
application's stored snapshots.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APIClient

from audit.admin import AuditedModelAdmin
from audit.models import AuditEvent, ImmutableAuditQuerySet
from audit.services import application_timeline, record_event
from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    SupportingDocument,
)
from leave.services.documents import (
    ACTION_DOCUMENT_REMOVED,
    add_document,
    remove_document,
)
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    TODAY,
    make_approver_chain,
    make_user,
)
from workflows.approval import decide
from workflows.models import Delegation, Workflow, WorkflowStage
from workflows.services import approve_delegation, reassign_application

HISTORY_URL = "/api/v1/applications/{id}/history/"
MY_HISTORY_URL = "/api/v1/leave/my/history/"


def upload_file(name, content=b"%PDF-1.4 test payload", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class Unit24TimelineFixtureMixin(StubProviderMixin):
    """Employee + approver chain fixture resolved by the workflow provider."""

    def setUpTimeline(self):
        self.stub = self.use_stub(today=TODAY)
        chain = make_approver_chain()
        self.supervisor = chain["supervisor"]
        self.hod = chain["hod"]
        self.dean = chain["dean"]
        self.registrar = chain["registrar"]
        self.dvc = chain["dvc"]
        self.hr = make_user(username="hr@test.luanar", role="hr")
        self.employee = make_user()
        self._name_users()
        self.stub.register_employee(self.employee)
        self.other = make_user(username="other@test.luanar")
        self.stub.register_employee(self.other)
        self.client = APIClient()
        self._dates = EARLIEST_ANNUAL_START
        patchers = [
            mock.patch("django.utils.timezone.localdate", return_value=TODAY),
            mock.patch("leave.providers.get_today", return_value=TODAY),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _name_users(self):
        names = {
            self.supervisor: ("Amos", "Banda"),
            self.hod: ("Beatrice", "Chanda"),
            self.dean: ("Charles", "Daka"),
            self.registrar: ("Doris", "Ezekiel"),
            self.dvc: ("Ernest", "Fumba"),
            self.hr: ("Faith", "Gondwe"),
        }
        for user, (first, last) in names.items():
            user.first_name = first
            user.last_name = last
            user.save(update_fields=["first_name", "last_name"])

    def submit_app(self, employee=None):
        from leave.services.submission import submit_application

        employee = employee or self.employee
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=self._dates,
            end_date=self._dates + timedelta(days=4),
            reason="Annual leave",
        )
        submit_application(user=employee, application_id=app.id)
        app.refresh_from_db()
        self._dates = self._dates + timedelta(days=10)
        return app

    def decide(self, app, approver, action="approve"):
        decide(
            application_id=app.id,
            actor=approver,
            action=action,
            comment="Approved." if action == "approve" else "Please revise.",
            expected_stage_version=app.current_stage.version,
        )
        app.refresh_from_db()
        return app


# ---------------------------------------------------------------------------
# AuditEvent immutability (ORM-level append-only)
# ---------------------------------------------------------------------------


class AuditEventImmutabilityTests(TestCase):
    def setUp(self):
        self.app = LeaveApplication.objects.create(
            employee=make_user(),
            status=LeaveApplication.Status.DRAFT,
        )
        self.event = record_event(
            actor=None,
            action="leave_application.submitted",
            target=self.app,
            prev_state="draft",
            new_state="submitted",
        )

    def test_model_delete_raises(self):
        with self.assertRaises(RuntimeError):
            self.event.delete()

    def test_save_after_load_raises(self):
        self.event.refresh_from_db()
        self.event.action = "tampered"
        with self.assertRaises(RuntimeError):
            self.event.save()

    def test_queryset_update_raises(self):
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.filter(pk=self.event.pk).update(action="tampered")

    def test_queryset_delete_raises(self):
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.filter(pk=self.event.pk).delete()

    def test_manager_update_and_delete_raise(self):
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.update(action="tampered")
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.delete()

    def test_queryset_class_is_immutable(self):
        self.assertIsInstance(AuditEvent.objects.all(), ImmutableAuditQuerySet)

    def test_event_survives_target_deletion(self):
        app_pk = self.app.pk
        self.app.delete()
        self.assertTrue(AuditEvent.objects.filter(object_id=str(app_pk)).exists())


# ---------------------------------------------------------------------------
# Draft-document removal regression (event must keep its object_id)
# ---------------------------------------------------------------------------


class DraftDocumentRemovalAuditTests(TestCase):
    def setUp(self):
        self.employee = make_user()
        self.other = make_user(username="other2@test.luanar")
        self.application = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.DRAFT,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            reason="Family visit",
        )

    def test_draft_removal_event_keeps_object_id_and_file_name(self):
        document = add_document(
            application_id=self.application.id,
            actor=self.employee,
            file=upload_file("support.pdf"),
        )
        remove_document(
            application_id=self.application.id,
            document_id=document.id,
            actor=self.employee,
        )

        events = AuditEvent.objects.filter(action=ACTION_DOCUMENT_REMOVED)
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.object_id, str(document.id))
        self.assertEqual(event.metadata["file_name"], "support.pdf")
        self.assertEqual(event.metadata["application_id"], str(self.application.id))

    def test_removal_event_survives_the_document_row_delete(self):
        document = add_document(
            application_id=self.application.id,
            actor=self.employee,
            file=upload_file("support.pdf"),
        )
        remove_document(
            application_id=self.application.id,
            document_id=document.id,
            actor=self.employee,
        )
        self.assertFalse(SupportingDocument.objects.filter(pk=document.pk).exists())
        event = AuditEvent.objects.get(action=ACTION_DOCUMENT_REMOVED)
        refreshed = AuditEvent.objects.get(pk=event.pk)
        self.assertEqual(refreshed.object_id, str(document.id))
        self.assertIsNone(refreshed.content_object)


# ---------------------------------------------------------------------------
# AuditedModelAdmin recorder
# ---------------------------------------------------------------------------


class AdminAuditRecorderTests(TestCase):
    """HR-config edits through the Django admin must write audit events."""

    def setUp(self):
        self.factory = RequestFactory()
        self.hr = make_user(username="hr-admin@test.luanar", role="hr")
        self.leave_type = LeaveType.objects.create(name="Annual Leave")

    def _request(self):
        request = self.factory.post("/admin/")
        request.user = self.hr
        return request

    def test_leave_rule_create_records_event(self):
        from leave.admin import LeaveRuleAdmin

        rule = LeaveRule(
            leave_type=self.leave_type,
            max_duration_days=30,
            effective_from=date(2026, 1, 1),
        )
        admin = LeaveRuleAdmin(LeaveRule, AdminSite())
        admin.save_model(self._request(), rule, form=None, change=False)

        event = AuditEvent.objects.get(action="leave.leaverule.created")
        self.assertEqual(event.actor, self.hr)
        self.assertEqual(event.object_id, str(rule.pk))
        self.assertEqual(event.metadata["summary"], str(rule))

    def test_leave_rule_update_records_before_after_diff(self):
        from leave.admin import LeaveRuleAdmin

        rule = LeaveRule.objects.create(
            leave_type=self.leave_type,
            max_duration_days=30,
            effective_from=date(2026, 1, 1),
        )
        admin = LeaveRuleAdmin(LeaveRule, AdminSite())
        rule.max_duration_days = 25
        admin.save_model(self._request(), rule, form=None, change=True)

        event = AuditEvent.objects.get(action="leave.leaverule.updated")
        self.assertEqual(event.object_id, str(rule.pk))
        before = event.metadata["before"]
        after = event.metadata["after"]
        self.assertEqual(before["max_duration_days"], 30)
        self.assertEqual(after["max_duration_days"], 25)

    def test_leave_rule_delete_records_before_snapshot(self):
        from leave.admin import LeaveRuleAdmin

        rule = LeaveRule.objects.create(
            leave_type=self.leave_type,
            max_duration_days=30,
            effective_from=date(2026, 1, 1),
        )
        pk = rule.pk
        admin = LeaveRuleAdmin(LeaveRule, AdminSite())
        request = self._request()
        admin.delete_model(request, rule)

        event = AuditEvent.objects.get(action="leave.leaverule.deleted")
        self.assertEqual(event.object_id, str(pk))
        self.assertEqual(event.metadata["before"]["max_duration_days"], 30)
        self.assertFalse(LeaveRule.objects.filter(pk=pk).exists())

    def test_workflow_inline_stage_creation_records_event(self):
        from workflows.admin import WorkflowAdmin, WorkflowStageInline
        from workflows.models import Workflow

        from django.contrib.auth.models import Permission

        self.hr.user_permissions.add(
            Permission.objects.get(codename="add_workflowstage")
        )
        workflow = Workflow.objects.create(name="Registry")
        request = self._request()
        request.META["HTTP_ACCEPT"] = "application/json"

        inline = WorkflowStageInline(Workflow, AdminSite())
        formset_cls = inline.get_formset(request, obj=workflow)
        data = {
            "stages-TOTAL_FORMS": "1",
            "stages-INITIAL_FORMS": "0",
            "stages-MIN_NUM_FORMS": "1",
            "stages-MAX_NUM_FORMS": "1000",
            "stages-0-id": "",
            "stages-0-order": "1",
            "stages-0-approver_role": "hod",
        }
        formset = formset_cls(
            data=data,
            instance=workflow,
            queryset=WorkflowStage.objects.filter(workflow=workflow),
        )
        self.assertTrue(formset.is_valid(), formset.non_form_errors())

        admin = WorkflowAdmin(Workflow, AdminSite())
        admin.save_formset(request, form=None, formset=formset, change=True)

        stage = WorkflowStage.objects.get(workflow=workflow)
        event = AuditEvent.objects.get(action="workflows.workflowstage.created")
        self.assertEqual(event.actor, self.hr)
        self.assertEqual(event.content_object, stage)
        self.assertEqual(
            event.metadata["after"]["approver_role"], "hod"
        )
        self.assertEqual(event.actor, self.hr)
        self.assertEqual(event.object_id, str(WorkflowStage.objects.get().pk))
        self.assertEqual(event.metadata["after"]["approver_role"], "hod")


# ---------------------------------------------------------------------------
# Timeline service + API
# ---------------------------------------------------------------------------


class ApplicationTimelineTests(Unit24TimelineFixtureMixin, TestCase):
    def setUp(self):
        self.setUpTimeline()
        self.app = self.submit_app()

    def test_entries_are_oldest_first(self):
        entries = application_timeline(self.app)
        actions = [entry["action"] for entry in entries]
        self.assertIn("leave_application.submitted", actions)
        self.assertIn("leave_application.workflow_assigned", actions)
        occurred = [entry["occurred_at"] for entry in entries]
        self.assertEqual(occurred, sorted(occurred))

    def test_entry_shape(self):
        entry = application_timeline(self.app)[0]
        self.assertEqual(
            set(entry),
            {
                "id",
                "kind",
                "action",
                "action_label",
                "occurred_at",
                "actor",
                "target_type",
                "state_transition",
                "summary",
                "metadata",
                "stage_order",
                "resubmission_number",
            },
        )
        self.assertEqual(entry["kind"], "submission")
        self.assertEqual(entry["state_transition"]["from"], "draft")
        self.assertEqual(entry["state_transition"]["to"], "submitted")

    def test_decision_events_render_with_approver_label(self):
        self.decide(self.app, self.hod)
        entries = application_timeline(self.app)
        decision = next(
            entry for entry in entries if entry["action"].startswith("leave_application.")
            and "approve" in entry["action"]
        )
        self.assertEqual(decision["kind"], "decision")
        self.assertIn(self.hod.get_full_name(), decision["action_label"])
        self.assertEqual(decision["stage_order"], 1)

    def test_document_events_are_included(self):
        draft = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.DRAFT,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            reason="Family visit",
        )
        document = add_document(
            application_id=draft.id,
            actor=self.employee,
            file=upload_file("letter.pdf"),
        )
        self.assertEqual(document.file_name, "letter.pdf")

        entries = application_timeline(draft)
        document_entry = next(
            entry for entry in entries if entry["kind"] == "document"
        )
        self.assertEqual(document_entry["action"], "document_uploaded")
        self.assertEqual(document_entry["target_type"], "supportingdocument")
        self.assertEqual(document_entry["summary"], "letter.pdf")
        self.assertEqual(document_entry["actor"]["id"], self.employee.pk)

    def test_delegation_events_are_excluded(self):
        delegation = Delegation.objects.create(
            approver=self.hod,
            delegate=self.dean,
            starts_on=TODAY,
            requested_by=self.hod,
            request_reason="Away.",
        )
        approve_delegation(
            delegation,
            self.hr,
            {"delegate": self.dean, "decision_reason": "Granted."},
        )
        entries = application_timeline(self.app)
        self.assertFalse(
            [entry for entry in entries if "delegation" in entry["action"]]
        )

    def test_cancellation_events_render_as_cancellation_kind(self):
        record_event(
            actor=self.employee,
            action="cancellation.requested",
            target=self.app,
            prev_state=self.app.status,
            new_state=self.app.status,
            metadata={"cancellation_request_id": "1", "comment": "Changed plans."},
        )
        entries = application_timeline(self.app)
        cancellation = next(
            entry for entry in entries if entry["action"] == "cancellation.requested"
        )
        self.assertEqual(cancellation["kind"], "cancellation")


class ApplicationHistoryAPITests(Unit24TimelineFixtureMixin, TestCase):
    def setUp(self):
        self.setUpTimeline()
        self.app = self.submit_app()

    def test_unauthenticated_is_401(self):
        for url in (HISTORY_URL.format(id=self.app.id), MY_HISTORY_URL):
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_owner_sees_full_payload(self):
        self.client.force_authenticate(self.employee)
        response = self.client.get(HISTORY_URL.format(id=self.app.id))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["application"]["id"], str(self.app.id))
        actions = [entry["action"] for entry in response.data["entries"]]
        self.assertIn("leave_application.submitted", actions)

    def test_stranger_is_404_not_403(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(HISTORY_URL.format(id=self.app.id))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_reached_approver_can_view_but_waiter_cannot(self):
        self.decide(self.app, self.hod)
        self.client.force_authenticate(self.dean)
        response = self.client.get(HISTORY_URL.format(id=self.app.id))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.client.force_authenticate(self.registrar)
        response = self.client.get(HISTORY_URL.format(id=self.app.id))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_hr_can_view_any_application(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(HISTORY_URL.format(id=self.app.id))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_draft_is_owner_only(self):
        draft = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.DRAFT,
        )
        self.client.force_authenticate(self.employee)
        self.assertEqual(
            self.client.get(HISTORY_URL.format(id=draft.id)).status_code,
            http_status.HTTP_200_OK,
        )
        self.client.force_authenticate(self.hr)
        self.assertEqual(
            self.client.get(HISTORY_URL.format(id=draft.id)).status_code,
            http_status.HTTP_404_NOT_FOUND,
        )

    def test_missing_application_is_404(self):
        import uuid

        self.client.force_authenticate(self.hr)
        response = self.client.get(HISTORY_URL.format(id=uuid.uuid4()))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_my_history_lists_only_own_applications(self):
        other_app = self.submit_app(employee=self.other)
        self.client.force_authenticate(self.employee)
        response = self.client.get(MY_HISTORY_URL)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = [row["application"]["id"] for row in response.data]
        self.assertIn(str(self.app.id), ids)
        self.assertNotIn(str(other_app.id), ids)


# ---------------------------------------------------------------------------
# Historical integrity: config edits never mutate a submitted application
# ---------------------------------------------------------------------------


class HistoricalIntegrityTests(Unit24TimelineFixtureMixin, TestCase):
    def setUp(self):
        self.setUpTimeline()
        self.app = self.submit_app()
        self.snapshot_before = dict(self.app.rules_snapshot)
        self.stages_before = [
            (stage.stage_order, stage.role, stage.role_label, stage.status)
            for stage in self.app.stages.all()
        ]

    def test_rule_edit_does_not_touch_snapshot_or_stages(self):
        rule = LeaveRule.objects.create(
            leave_type=LeaveType.objects.create(name="Annual Leave Belated"),
            max_duration_days=30,
            effective_from=date(2026, 1, 1),
        )
        rule.max_duration_days = 10
        rule.save()

        self.app.refresh_from_db()
        self.assertEqual(self.app.rules_snapshot, self.snapshot_before)
        self.assertEqual(
            [
                (stage.stage_order, stage.role, stage.role_label, stage.status)
                for stage in self.app.stages.all()
            ],
            self.stages_before,
        )

    def test_entitlement_edit_does_not_touch_snapshot(self):
        entitlement = GradeEntitlement.objects.create(
            grade_start="A", grade_end="D", days=24, effective_from=date(2026, 1, 1)
        )
        entitlement.days = 18
        entitlement.save()

        self.app.refresh_from_db()
        self.assertEqual(self.app.rules_snapshot, self.snapshot_before)

    def test_workflow_mutation_does_not_touch_stage_snapshot(self):
        workflow = Workflow.objects.create(name="Mutated workflow")
        stage = WorkflowStage.objects.create(
            workflow=workflow, order=1, approver_role="hod"
        )
        stage.approver_role = "dean"
        stage.save()

        self.app.refresh_from_db()
        self.assertEqual(
            [
                (item.stage_order, item.role, item.role_label, item.status)
                for item in self.app.stages.all()
            ],
            self.stages_before,
        )

    def test_reassignment_updates_spine_but_not_stage_snapshot(self):
        submitted = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-TLS",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 6),
            reason="Reassignment fixture",
            submitted_at=timezone.now(),
        )
        reassign_application(
            application=submitted,
            to_approver=self.dean,
            actor=self.hr,
            reason="On leave of absence.",
        )
        submitted.refresh_from_db()
        self.assertEqual(submitted.current_approver, self.dean)

        entries = application_timeline(submitted)
        reassignment = next(
            entry for entry in entries if entry["action"] == "application.reassigned"
        )
        self.assertEqual(reassignment["kind"], "reassignment")
        self.assertEqual(
            reassignment["summary"], f"Reassigned to {self.dean.get_full_name()}"
        )
        self.assertEqual(
            reassignment["summary"],
            f"Reassigned to {(self.dean.get_full_name() or self.dean.username)}",
        )