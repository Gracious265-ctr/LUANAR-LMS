import uuid
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.forms.models import inlineformset_factory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication
from users.models import User

from .admin import (
    DelegationAdmin,
    ReassignmentAdmin,
    WorkflowAdmin,
    WorkflowAdminForm,
    WorkflowStageForm,
    WorkflowStageInlineFormSet,
)
from .models import Delegation, Reassignment, Workflow, WorkflowStage
from .services import (
    DelegationActionError,
    ReassignmentError,
    StageSequenceError,
    active_delegation_for,
    approve_delegation,
    cancel_delegation,
    find_conflicting_delegation,
    find_conflicting_workflow,
    is_approver_user,
    missing_approver_roles,
    normalize_stage_sequence,
    open_request_exists,
    reassign_application,
    reject_delegation,
    resolve_delegate_user,
    scopes_overlap,
    validate_workflow_for_activation,
)

SEED_PASSWORD = "testpass123"

VALID_STAGES = [
    {"order": 1, "approver_role": "supervisor"},
    {"order": 2, "approver_role": "hod"},
    {"order": 3, "approver_role": "registrar"},
    {"order": 4, "approver_role": "dvc"},
]


class StageSequenceTests(TestCase):
    """Service-level workflow stage-sequence validation."""

    def test_valid_sequence_normalizes_to_one_based_order(self):
        result = normalize_stage_sequence(VALID_STAGES)
        self.assertEqual(
            [stage["approver_role"] for stage in result],
            ["supervisor", "hod", "registrar", "dvc"],
        )
        self.assertEqual([stage["order"] for stage in result], [1, 2, 3, 4])

    def test_empty_sequence_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_stage_sequence([])
        self.assertEqual(ctx.exception.field, "stages")

    def test_unknown_approver_role_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_stage_sequence([{"order": 1, "approver_role": "employee"}])
        self.assertEqual(ctx.exception.field, "approver_role")

    def test_repeated_approver_role_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_stage_sequence(
                [{"order": 1, "approver_role": "hod"}, {"order": 2, "approver_role": "hod"}]
            )
        self.assertEqual(ctx.exception.field, "stages")

    def test_non_positive_order_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_stage_sequence([{"order": 0, "approver_role": "hod"}])
        self.assertEqual(ctx.exception.field, "order")

    def test_duplicate_order_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_stage_sequence(
                [{"order": 1, "approver_role": "hod"}, {"order": 1, "approver_role": "registrar"}]
            )
        self.assertEqual(ctx.exception.field, "order")


class WorkflowEndpointTests(TestCase):
    """HR-only CRUD and validation for approval workflows."""

    @classmethod
    def setUpTestData(cls):
        cls.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        cls.employee_user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )

        cls.workflow = Workflow.objects.create(
            name="Academic approval",
            employee_category="academic",
            department="",
        )
        Workflow.objects.create(
            name="Administration approval",
            employee_category="administration",
            department="",
        )
        for stage in VALID_STAGES:
            WorkflowStage.objects.create(workflow=cls.workflow, **stage)

        cls.list_url = "/api/v1/workflows/"
        cls.detail_url = f"/api/v1/workflows/{cls.workflow.id}/"

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]

    def test_list_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.post(self.list_url, {}).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_detail_and_update_require_authentication(self):
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.patch(self.detail_url, {}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

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

    def test_hr_can_list_workflows_ordered_by_name(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data["results"]]  # type: ignore[index]
        self.assertEqual(
            names, ["Academic approval", "Administration approval"]
        )

    def test_hr_can_retrieve_workflow_with_ordered_stages(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stages = response.data["stages"]  # type: ignore[index]
        self.assertEqual(
            [stage["approver_role"] for stage in stages],
            ["supervisor", "hod", "registrar", "dvc"],
        )
        self.assertEqual([stage["order"] for stage in stages], [1, 2, 3, 4])

    def test_hr_can_create_workflow_with_stages(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "name": "Dean office approval",
                "employee_category": "academic",
                "department": "Faculty of Science",
                "stages": [
                    {"order": 1, "approver_role": "hod"},
                    {"order": 2, "approver_role": "dean"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["name"], "Dean office approval")
        self.assertEqual(payload["department"], "Faculty of Science")
        self.assertEqual(
            [stage["approver_role"] for stage in payload["stages"]],
            ["hod", "dean"],
        )
        self.assertTrue(
            WorkflowStage.objects.filter(
                workflow_id=payload["id"], order=2, approver_role="dean"
            ).exists()
        )

    def test_create_blank_category_and_department_means_any(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "name": "University-wide approval",
                "employee_category": "",
                "department": "",
                "stages": [{"order": 1, "approver_role": "registrar"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["employee_category"], "")
        self.assertEqual(response.json()["department"], "")

    def test_patch_replaces_stages(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            self.detail_url,
            {
                "stages": [
                    {"order": 1, "approver_role": "dean"},
                    {"order": 2, "approver_role": "registrar"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stages = response.json()["stages"]
        self.assertEqual(
            [stage["approver_role"] for stage in stages], ["dean", "registrar"]
        )
        self.assertEqual(WorkflowStage.objects.filter(workflow=self.workflow).count(), 2)

    def test_patch_normalizes_submitted_order_to_sequence(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            self.detail_url,
            {
                "stages": [
                    {"order": 3, "approver_role": "hod"},
                    {"order": 1, "approver_role": "registrar"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [stage["approver_role"] for stage in response.json()["stages"]],
            ["hod", "registrar"],
        )
        self.assertEqual(
            [stage["order"] for stage in response.json()["stages"]], [1, 2]
        )

    def test_missing_name_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "employee_category": "academic",
                "stages": [{"order": 1, "approver_role": "hod"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())

    def test_duplicate_name_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "name": "Academic approval",
                "stages": [{"order": 1, "approver_role": "hod"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())

    def test_missing_stages_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, {"name": "No stages", "employee_category": "academic"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stages", response.json())

    def test_empty_stages_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, {"name": "Empty stages", "stages": []}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stages", response.json())

    def test_invalid_approver_role_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"name": "Bad role", "stages": [{"order": 1, "approver_role": "employee"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("approver_role", response.json()["stages"]["0"])

    def test_repeated_approver_role_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "name": "Repeated role",
                "stages": [
                    {"order": 1, "approver_role": "hod"},
                    {"order": 2, "approver_role": "hod"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stages", response.json())

    def test_invalid_order_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {"name": "Bad order", "stages": [{"order": 0, "approver_role": "hod"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order", response.json()["stages"]["0"])

    def test_duplicate_order_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            {
                "name": "Duplicate order",
                "stages": [
                    {"order": 1, "approver_role": "hod"},
                    {"order": 1, "approver_role": "dean"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order", response.json())

    def test_delete_not_supported(self):
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(
            self.client.delete(self.detail_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )


class WorkflowAdminTests(TestCase):
    """Workflow admin guards for stage sequences."""

    @classmethod
    def setUpTestData(cls):
        cls.workflow = Workflow.objects.create(name="Admin workflow")

    def setUp(self):
        self.site = AdminSite()

    def test_stage_order_must_be_at_least_one(self):
        StageInlineForm = inlineformset_factory(
            Workflow,
            WorkflowStage,
            form=WorkflowStageForm,
            formset=WorkflowStageInlineFormSet,
            fields=["order", "approver_role"],
            extra=1,
        )
        formset = StageInlineForm(
            data={
                "stages-TOTAL_FORMS": "1",
                "stages-INITIAL_FORMS": "0",
                "stages-MIN_NUM_FORMS": "1",
                "stages-MAX_NUM_FORMS": "1000",
                "stages-0-order": "0",
                "stages-0-approver_role": "hod",
            },
            instance=Workflow(),
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("order", formset.errors[0])

    def test_repeated_approver_role_rejected(self):
        StageInlineForm = inlineformset_factory(
            Workflow,
            WorkflowStage,
            form=WorkflowStageForm,
            formset=WorkflowStageInlineFormSet,
            fields=["order", "approver_role"],
            extra=1,
        )
        formset = StageInlineForm(
            data={
                "stages-TOTAL_FORMS": "2",
                "stages-INITIAL_FORMS": "0",
                "stages-MIN_NUM_FORMS": "1",
                "stages-MAX_NUM_FORMS": "1000",
                "stages-0-order": "1",
                "stages-0-approver_role": "hod",
                "stages-1-order": "2",
                "stages-1-approver_role": "hod",
            },
            instance=Workflow(),
        )
        self.assertFalse(formset.is_valid())
        self.assertTrue(
            any("once" in error for error in formset.non_form_errors())
        )

    def test_admin_list_prefetches_stages_for_summary(self):
        self.workflow.stages.create(order=1, approver_role="hod")
        admin = WorkflowAdmin(Workflow, self.site)
        queryset = admin.get_queryset(None)
        with self.assertNumQueries(2):
            summary = admin.stage_summary(queryset.get(pk=self.workflow.pk))
        self.assertEqual(summary, "hod")


def make_active_user(role: str, username: str) -> User:
    return User.objects.create_user(
        username=username,
        email=username,
        password=SEED_PASSWORD,
        first_name="Test",
        last_name="Approver",
        role=role,
    )


class WorkflowActivationServiceTests(TestCase):
    """Service-level workflow activation validation."""

    def test_scopes_overlap_equal_and_any(self):
        self.assertTrue(
            scopes_overlap(("academic", ""), ("academic", "Faculty of Science"))
        )
        self.assertTrue(scopes_overlap(("", ""), ("administration", "Registry")))
        self.assertTrue(
            scopes_overlap(("academic", "Faculty of Science"), ("academic", ""))
        )

    def test_scopes_do_not_overlap_when_a_dimension_differs(self):
        self.assertFalse(
            scopes_overlap(("academic", "A"), ("administration", "A"))
        )
        self.assertFalse(scopes_overlap(("academic", "A"), ("academic", "B")))

    def test_missing_approver_roles_lists_roles_without_active_user(self):
        make_active_user(User.Role.HR, "hr@test.luanar")
        stages = [
            {"order": 1, "approver_role": "hr"},
            {"order": 2, "approver_role": "dean"},
        ]
        self.assertEqual(missing_approver_roles(stages), ["dean"])

    def test_missing_approver_roles_treats_inactive_users_as_missing(self):
        user = make_active_user(User.Role.SUPERVISOR, "supervisor@test.luanar")
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(
            missing_approver_roles([{"order": 1, "approver_role": "supervisor"}]),
            ["supervisor"],
        )

    def test_find_conflicting_workflow_excludes_self_and_drafts(self):
        today = timezone.localdate()
        applying = Workflow.objects.create(
            name="Applying",
            employee_category="administration",
            effective_from=today,
        )
        Workflow.objects.create(name="Draft", employee_category="administration")

        conflict = find_conflicting_workflow(None, ("administration", ""))
        self.assertEqual(conflict, applying)
        self.assertIsNone(
            find_conflicting_workflow(applying.pk, ("administration", ""))
        )

    def test_find_conflicting_workflow_matches_any_category(self):
        today = timezone.localdate()
        applying = Workflow.objects.create(
            name="Any scope",
            employee_category="",
            department="",
            effective_from=today,
        )
        self.assertEqual(
            find_conflicting_workflow(None, ("academic", "Faculty of Science")),
            applying,
        )

    def test_inactive_workflow_does_not_conflict(self):
        today = timezone.localdate()
        Workflow.objects.create(
            name="Inactive",
            employee_category="administration",
            effective_from=today,
            is_active=False,
        )
        self.assertIsNone(
            find_conflicting_workflow(None, ("administration", ""))
        )

    def test_validate_workflow_for_activation_reports_missing_and_conflict(self):
        today = timezone.localdate()
        Workflow.objects.create(
            name="Existing",
            employee_category="administration",
            effective_from=today,
        )
        issues = validate_workflow_for_activation(
            None,
            ("administration", ""),
            [{"order": 1, "approver_role": "dean"}],
        )
        self.assertEqual(len(issues), 2)
        by_field = {issue.field: issue.message for issue in issues}
        self.assertIn("Dean", by_field[None])
        self.assertIn("Existing", by_field["effective_from"])


class WorkflowActivationEndpointTests(TestCase):
    """Scheduling, activating, and conflict validation through the API."""

    @classmethod
    def setUpTestData(cls):
        cls.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        cls.list_url = "/api/v1/workflows/"

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.client.force_authenticate(user=self.hr_user)

    def _payload(self, **overrides) -> dict:
        payload = {
            "name": "Workflow",
            "employee_category": "administration",
            "department": "",
            "stages": [{"order": 1, "approver_role": "hr"}],
        }
        payload.update(overrides)
        return payload

    def test_draft_create_needs_no_approvers(self):
        response = self.client.post(
            self.list_url,
            self._payload(stages=[{"order": 1, "approver_role": "dean"}]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["state"], "draft")
        self.assertIsNone(response.json()["effective_from"])

    def test_scheduling_future_date_is_scheduled_state(self):
        future = (timezone.localdate() + timedelta(days=30)).isoformat()
        response = self.client.post(
            self.list_url,
            self._payload(effective_from=future, is_active=True),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["state"], "scheduled")
        self.assertEqual(response.json()["effective_from"], future)

    def test_scheduling_today_is_active_state(self):
        response = self.client.post(
            self.list_url,
            self._payload(
                effective_from=timezone.localdate().isoformat(), is_active=True
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["state"], "active")

    def test_deactivation_reports_inactive_state(self):
        response = self.client.post(
            self.list_url,
            self._payload(
                effective_from=timezone.localdate().isoformat(), is_active=True
            ),
            format="json",
        )
        workflow_id = response.json()["id"]
        response = self.client.patch(
            f"/api/v1/workflows/{workflow_id}/",
            {
                "is_active": False,
                "stages": [{"order": 1, "approver_role": "hr"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["state"], "inactive")

    def test_activation_without_active_approver_rejected(self):
        response = self.client.post(
            self.list_url,
            self._payload(
                stages=[{"order": 1, "approver_role": "dean"}],
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Dean", response.json()["detail"][0])

    def test_activation_with_overlapping_scope_rejected(self):
        self.client.post(
            self.list_url,
            self._payload(
                name="First",
                employee_category="administration",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        response = self.client.post(
            self.list_url,
            self._payload(
                name="Second",
                employee_category="",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effective_from", response.json())
        self.assertIn("First", response.json()["effective_from"][0])

    def test_deactivating_frees_scope_for_replacement(self):
        first = self.client.post(
            self.list_url,
            self._payload(
                name="First",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        self.client.patch(
            f"/api/v1/workflows/{first.json()['id']}/",
            {
                "is_active": False,
                "stages": [{"order": 1, "approver_role": "hr"}],
            },
            format="json",
        )
        response = self.client.post(
            self.list_url,
            self._payload(
                name="Replacement",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_editing_active_workflow_into_conflict_rejected(self):
        self.client.post(
            self.list_url,
            self._payload(
                name="Administration",
                employee_category="administration",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        academic = self.client.post(
            self.list_url,
            self._payload(
                name="Academic",
                employee_category="academic",
                effective_from=timezone.localdate().isoformat(),
                is_active=True,
            ),
            format="json",
        )
        response = self.client.patch(
            f"/api/v1/workflows/{academic.json()['id']}/",
            {
                "employee_category": "administration",
                "stages": [{"order": 1, "approver_role": "hr"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effective_from", response.json())

    def test_editing_draft_without_effective_date_is_allowed(self):
        draft = self.client.post(
            self.list_url,
            self._payload(stages=[{"order": 1, "approver_role": "dean"}]),
            format="json",
        )
        response = self.client.patch(
            f"/api/v1/workflows/{draft.json()['id']}/",
            {
                "department": "Registry",
                "stages": [{"order": 1, "approver_role": "dean"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["state"], "draft")


class WorkflowActivationAdminTests(TestCase):
    """Admin form guards for activation validation."""

    def setUp(self):
        self.site = AdminSite()
        self.today = timezone.localdate()

    def _form(self, workflow: Workflow, **overrides) -> WorkflowAdminForm:
        data = {
            "name": workflow.name,
            "employee_category": workflow.employee_category or "",
            "department": workflow.department or "",
            "effective_from": "",
            "is_active": False,
        }
        data.update(overrides)
        return WorkflowAdminForm(data=data, instance=workflow)

    def test_form_rejects_conflict(self):
        Workflow.objects.create(
            name="Existing",
            employee_category="administration",
            effective_from=self.today,
        )
        workflow = Workflow.objects.create(
            name="Replacement", employee_category="administration"
        )
        form = self._form(
            workflow,
            effective_from=self.today.isoformat(),
            is_active=True,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(
            any("Existing" in error for error in form.non_field_errors())
        )

    def test_form_rejects_missing_approver(self):
        workflow = Workflow.objects.create(name="Needs dean")
        workflow.stages.create(order=1, approver_role="dean")
        form = self._form(
            workflow,
            effective_from=self.today.isoformat(),
            is_active=True,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(
            any("Dean" in error for error in form.non_field_errors())
        )

    def test_form_allows_draft_without_approvers(self):
        workflow = Workflow.objects.create(name="Draft workflow")
        workflow.stages.create(order=1, approver_role="dean")
        form = self._form(workflow)
        self.assertTrue(form.is_valid())

    def test_form_allows_activation_with_active_approver(self):
        make_active_user(User.Role.HR, "hr-admin@test.luanar")
        workflow = Workflow.objects.create(name="Ready workflow")
        workflow.stages.create(order=1, approver_role="hr")
        form = self._form(
            workflow,
            effective_from=self.today.isoformat(),
            is_active=True,
        )
        self.assertTrue(form.is_valid())


def make_delegation(
    approver: User,
    starts_on,
    ends_on=None,
    status=Delegation.Status.REQUESTED,
    delegate: User | None = None,
) -> Delegation:
    return Delegation.objects.create(
        approver=approver,
        delegate=delegate,
        starts_on=starts_on,
        ends_on=ends_on,
        requested_by=approver,
        status=status,
    )


class DelegationModelStateTests(TestCase):
    """Derived delegation lifecycle states."""

    @classmethod
    def setUpTestData(cls):
        cls.hr = make_active_user(User.Role.HR, "hr-deleg@test.luanar")
        cls.dean = make_active_user(User.Role.DEAN, "dean-deleg@test.luanar")
        cls.hod = make_active_user(User.Role.HOD, "hod-deleg@test.luanar")

    def setUp(self):
        self.today = timezone.localdate()

    def test_requested_state(self):
        delegation = make_delegation(self.dean, self.today)
        self.assertEqual(delegation.state, "requested")
        self.assertEqual(delegation.status, Delegation.Status.REQUESTED)

    def test_scheduled_state_for_future_start(self):
        delegation = make_delegation(
            self.dean,
            self.today + timedelta(days=5),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        self.assertEqual(delegation.state, "scheduled")

    def test_active_state_when_period_covers_today(self):
        delegation = make_delegation(
            self.dean,
            self.today,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        self.assertEqual(delegation.state, "active")

    def test_active_state_for_open_ended_approval(self):
        delegation = make_delegation(
            self.dean,
            self.today - timedelta(days=1),
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        self.assertEqual(delegation.state, "active")

    def test_ended_state_after_the_end_date(self):
        delegation = make_delegation(
            self.dean,
            self.today - timedelta(days=10),
            self.today - timedelta(days=5),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        self.assertEqual(delegation.state, "ended")

    def test_rejected_and_cancelled_states(self):
        rejected = make_delegation(
            self.dean, self.today, status=Delegation.Status.REJECTED
        )
        cancelled = make_delegation(
            self.dean,
            self.today,
            status=Delegation.Status.CANCELLED,
            delegate=self.hod,
        )
        self.assertEqual(rejected.state, "rejected")
        self.assertEqual(cancelled.state, "cancelled")

    def test_ends_on_must_not_precede_starts_on(self):
        with self.assertRaises(Exception):
            make_delegation(self.dean, self.today, self.today - timedelta(days=1))


class DelegationServiceTests(TestCase):
    """Service-level delegation behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.hr = make_active_user(User.Role.HR, "hr-svc@test.luanar")
        cls.dean = make_active_user(User.Role.DEAN, "dean-svc@test.luanar")
        cls.hod = make_active_user(User.Role.HOD, "hod-svc@test.luanar")
        cls.employee = make_active_user(
            User.Role.EMPLOYEE, "employee-svc@test.luanar"
        )

    def setUp(self):
        self.today = timezone.localdate()

    def test_is_approver_user(self):
        self.assertTrue(is_approver_user(self.dean))
        self.assertTrue(is_approver_user(self.hr))
        self.assertFalse(is_approver_user(self.employee))
        self.assertFalse(is_approver_user(None))

    def test_resolve_delegate_user_accepts_valid_delegate(self):
        delegate = resolve_delegate_user(self.dean, self.hod.pk)
        self.assertEqual(delegate, self.hod)

    def test_resolve_delegate_user_rejects_self_inactive_and_employee(self):
        self.assertIsNone(resolve_delegate_user(self.dean, self.dean.pk))
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        self.assertIsNone(resolve_delegate_user(self.dean, self.employee.pk))
        self.assertIsNone(resolve_delegate_user(self.dean, None))
        self.assertIsNone(resolve_delegate_user(self.dean, 99999))

    def test_open_request_exists(self):
        make_delegation(self.dean, self.today)
        self.assertTrue(open_request_exists(self.dean.pk))
        self.assertFalse(open_request_exists(self.hod.pk))

    def test_find_conflicting_delegation_detects_overlap(self):
        approved = make_delegation(
            self.dean,
            self.today,
            self.today + timedelta(days=10),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        conflict = find_conflicting_delegation(
            None, self.dean.pk, self.today + timedelta(days=5), None
        )
        self.assertEqual(conflict, approved)
        self.assertIsNone(
            find_conflicting_delegation(
                approved.pk, self.dean.pk, self.today + timedelta(days=5), None
            )
        )

    def test_find_conflicting_delegation_treats_open_ended_as_infinite(self):
        make_delegation(
            self.dean,
            self.today,
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        conflict = find_conflicting_delegation(
            None, self.dean.pk, self.today + timedelta(days=30), None
        )
        self.assertIsNotNone(conflict)

    def test_find_conflicting_delegation_ignores_rejected_and_cancelled(self):
        make_delegation(
            self.dean,
            self.today,
            None,
            status=Delegation.Status.CANCELLED,
            delegate=self.hod,
        )
        self.assertIsNone(
            find_conflicting_delegation(None, self.dean.pk, self.today, None)
        )

    def test_conflicting_delegation_only_matches_approved(self):
        make_delegation(self.dean, self.today, None)
        self.assertIsNone(
            find_conflicting_delegation(None, self.dean.pk, self.today, None)
        )

    def test_active_delegation_for_returns_current_cover(self):
        make_delegation(
            self.dean,
            self.today - timedelta(days=1),
            self.today + timedelta(days=5),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        delegation = active_delegation_for(self.dean)
        self.assertIsNotNone(delegation)
        self.assertEqual(delegation.delegate, self.hod)

    def test_active_delegation_for_none_when_ended_not_started_or_cancelled(self):
        make_delegation(
            self.dean,
            self.today - timedelta(days=10),
            self.today - timedelta(days=5),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        make_delegation(
            self.hod,
            self.today + timedelta(days=5),
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.dean,
        )
        make_delegation(
            self.hr,
            self.today,
            None,
            status=Delegation.Status.CANCELLED,
            delegate=self.dean,
        )
        self.assertIsNone(active_delegation_for(self.dean))
        self.assertIsNone(active_delegation_for(self.hod))
        self.assertIsNone(active_delegation_for(self.hr))

    def test_approve_delegation_sets_delegate_status_and_decision(self):
        delegation = make_delegation(self.dean, self.today)
        approve_delegation(
            delegation, self.hr, {"delegate": self.hod, "decision_reason": "Approved"}
        )
        delegation.refresh_from_db()
        self.assertEqual(delegation.status, Delegation.Status.APPROVED)
        self.assertEqual(delegation.delegate, self.hod)
        self.assertEqual(delegation.decided_by, self.hr)
        self.assertEqual(delegation.decision_reason, "Approved")
        self.assertIsNotNone(delegation.decided_at)

    def test_approve_delegation_requires_reason_and_delegate(self):
        delegation = make_delegation(self.dean, self.today)
        with self.assertRaises(DelegationActionError) as ctx:
            approve_delegation(delegation, self.hr, {"delegate": self.hod})
        self.assertEqual(ctx.exception.field, "decision_reason")
        with self.assertRaises(DelegationActionError) as ctx:
            approve_delegation(
                delegation, self.hr, {"delegate": None, "decision_reason": "ok"}
            )
        self.assertEqual(ctx.exception.field, "delegate")

    def test_approve_delegation_rejects_overlap(self):
        make_delegation(
            self.dean,
            self.today,
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        delegation = make_delegation(
            self.dean, self.today + timedelta(days=3), None
        )
        with self.assertRaises(DelegationActionError) as ctx:
            approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
            )
        self.assertEqual(ctx.exception.field, "detail")
        self.assertIn("overlaps", ctx.exception.message)

    def test_approve_transitions_once_only(self):
        delegation = make_delegation(self.dean, self.today)
        approve_delegation(
            delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
        )
        with self.assertRaises(DelegationActionError):
            approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
            )

    def test_reject_delegation_records_decision(self):
        delegation = make_delegation(self.dean, self.today)
        reject_delegation(delegation, self.hr, {"decision_reason": "Not needed"})
        delegation.refresh_from_db()
        self.assertEqual(delegation.status, Delegation.Status.REJECTED)
        self.assertEqual(delegation.decided_by, self.hr)
        self.assertEqual(delegation.decision_reason, "Not needed")

    def test_reject_delegation_requires_reason_and_requested_state(self):
        delegation = make_delegation(self.dean, self.today)
        with self.assertRaises(DelegationActionError) as ctx:
            reject_delegation(delegation, self.hr, {})
        self.assertEqual(ctx.exception.field, "decision_reason")
        delegation.status = Delegation.Status.APPROVED
        delegation.save(update_fields=["status"])
        with self.assertRaises(DelegationActionError):
            reject_delegation(delegation, self.hr, {"decision_reason": "ok"})

    def test_cancel_delegation_stops_cover(self):
        delegation = make_delegation(
            self.dean,
            self.today,
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        self.assertIsNotNone(active_delegation_for(self.dean))
        cancel_delegation(delegation, self.hr, {"decision_reason": "Delegate returned"})
        delegation.refresh_from_db()
        self.assertEqual(delegation.status, Delegation.Status.CANCELLED)
        self.assertIsNone(active_delegation_for(self.dean))

    def test_cancel_rejects_requested_and_ended(self):
        requested = make_delegation(self.dean, self.today)
        with self.assertRaises(DelegationActionError) as ctx:
            cancel_delegation(requested, self.hr, {"decision_reason": "ok"})
        self.assertEqual(ctx.exception.field, "detail")

        ended = make_delegation(
            self.dean,
            self.today - timedelta(days=10),
            self.today - timedelta(days=5),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        with self.assertRaises(DelegationActionError) as ctx:
            cancel_delegation(ended, self.hr, {"decision_reason": "ok"})
        self.assertIn("completed", ctx.exception.message)

    def test_cancel_requires_reason(self):
        delegation = make_delegation(
            self.dean,
            self.today,
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        with self.assertRaises(DelegationActionError) as ctx:
            cancel_delegation(delegation, self.hr, {})
        self.assertEqual(ctx.exception.field, "decision_reason")


class DelegationEndpointTests(TestCase):
    """Delegation request creation, HR decisions, and filtering via the API."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password=SEED_PASSWORD,
            first_name="Hana",
            last_name="HR",
            role=User.Role.HR,
        )
        self.dean = User.objects.create_user(
            username="dean@test.luanar",
            email="dean@test.luanar",
            password=SEED_PASSWORD,
            first_name="Dean",
            last_name="Dept",
            role=User.Role.DEAN,
        )
        self.hod = User.objects.create_user(
            username="hod@test.luanar",
            email="hod@test.luanar",
            password=SEED_PASSWORD,
            first_name="Hod",
            last_name="Head",
            role=User.Role.HOD,
        )
        self.employee = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password=SEED_PASSWORD,
            first_name="Emp",
            last_name="Loyee",
            role=User.Role.EMPLOYEE,
        )
        self.today = timezone.localdate().isoformat()
        self.list_url = "/api/v1/delegations/"

    def _create_payload(self, **overrides) -> dict:
        payload = {
            "approver": self.dean.id,
            "delegate": self.hod.id,
            "starts_on": self.today,
            "ends_on": None,
        }
        payload.update(overrides)
        return payload

    def _delegation(self, **kwargs) -> int:
        return make_delegation(
            self.dean,
            kwargs.pop("starts_on", timezone.localdate()),
            kwargs.pop("ends_on", None),
            status=kwargs.pop("status", Delegation.Status.REQUESTED),
            **kwargs,
        ).pk

    def test_list_and_retrieve_require_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        delegation_id = self._delegation()
        self.assertEqual(
            self.client.get(f"/api/v1/delegations/{delegation_id}/").status_code, 401
        )

    def test_create_requires_authentication_and_denies_employee(self):
        self.assertEqual(self.client.post(self.list_url, {}).status_code, 401)
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            self.list_url, self._create_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approver_self_service_forces_own_approver(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.post(
            self.list_url,
            {"approver": self.hod.id, "starts_on": self.today},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["approver"], self.dean.id)
        self.assertEqual(response.json()["requested_by"], self.dean.id)
        self.assertEqual(response.json()["state"], "requested")
        self.assertEqual(response.json()["approver_name"], "Dean Dept")

    def test_hr_can_create_request_on_behalf(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            self._create_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["approver"], self.dean.id)
        self.assertEqual(payload["delegate"], self.hod.id)
        self.assertEqual(payload["requested_by"], self.hr_user.id)
        self.assertEqual(payload["approver_role"], "dean")

    def test_hr_create_requires_active_approver_role(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, self._create_payload(approver=self.employee.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("approver", response.json())

    def test_create_rejects_invalid_delegate(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, self._create_payload(delegate=self.employee.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delegate", response.json())

    def test_create_rejects_self_delegation(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url, self._create_payload(delegate=self.dean.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delegate", response.json())

    def test_create_rejects_end_before_start(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self.list_url,
            self._create_payload(ends_on=timezone.localdate() - timedelta(days=1)),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ends_on", response.json())

    def test_create_rejects_second_open_request_for_same_approver(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(self.list_url, self._create_payload(), format="json")
        response = self.client.post(
            self.list_url, self._create_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("approver", response.json())

    def test_list_and_retrieve_are_hr_only(self):
        self._delegation()
        self.client.force_authenticate(user=self.dean)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)

    def test_list_filters_by_state_and_searches_approver(self):
        self.client.force_authenticate(user=self.hr_user)
        make_delegation(
            self.dean, timezone.localdate(), status=Delegation.Status.APPROVED, delegate=self.hod
        )
        make_delegation(
            self.hod,
            timezone.localdate(),
            status=Delegation.Status.REJECTED,
        )
        active = self.client.get(self.list_url, {"state": "active"})
        self.assertEqual(active.json()["count"], 1)
        self.assertEqual(active.json()["results"][0]["approver"], self.dean.id)
        rejected = self.client.get(self.list_url, {"state": "rejected"})
        self.assertEqual(rejected.json()["count"], 1)
        self.assertEqual(rejected.json()["results"][0]["approver"], self.hod.id)
        searched = self.client.get(self.list_url, {"approver": "Dean"})
        self.assertEqual(searched.json()["count"], 1)

    def test_approve_happy_path(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation()
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"delegate": self.hod.id, "decision_reason": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["state"], "active")
        self.assertEqual(payload["delegate"], self.hod.id)
        self.assertEqual(payload["delegate_name"], "Hod Head")
        self.assertEqual(payload["decided_by"], self.hr_user.id)
        self.assertEqual(payload["decision_reason"], "Approved")

    def test_approve_requires_reason_and_delegate(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation()
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"decision_reason": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("decision_reason", response.json())
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"delegate": self.hod.id},
            format="json",
        )
        self.assertIn("decision_reason", response.json())

    def test_approve_rejects_overlapping_approved_delegation(self):
        self.client.force_authenticate(user=self.hr_user)
        make_delegation(
            self.dean,
            timezone.localdate(),
            None,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        delegation_id = self._delegation(
            starts_on=timezone.localdate() + timedelta(days=3)
        )
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"delegate": self.hod.id, "decision_reason": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("overlaps", response.json()["detail"][0])

    def test_approve_only_from_requested_state(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation(status=Delegation.Status.REJECTED)
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/approve/",
            {"delegate": self.hod.id, "decision_reason": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requested", response.json()["detail"][0])

    def test_reject_happy_path(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation()
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/reject/",
            {"decision_reason": "Not required"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertEqual(response.json()["state"], "rejected")
        self.assertEqual(response.json()["decision_reason"], "Not required")

    def test_reject_requires_reason(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation()
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/reject/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("decision_reason", response.json())

    def test_cancel_happy_path_ends_cover(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation(status=Delegation.Status.APPROVED, delegate=self.hod)
        self.assertIsNotNone(active_delegation_for(self.dean))
        response = self.client.post(
            f"/api/v1/delegations/{delegation_id}/cancel/",
            {"decision_reason": "Delegate returned early"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertEqual(response.json()["state"], "cancelled")
        self.assertIsNone(active_delegation_for(self.dean))

    def test_cancel_rejects_requested_and_ended(self):
        self.client.force_authenticate(user=self.hr_user)
        requested_id = self._delegation()
        response = self.client.post(
            f"/api/v1/delegations/{requested_id}/cancel/",
            {"decision_reason": "Nope"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        ended_id = self._delegation(
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
            starts_on=timezone.localdate() - timedelta(days=10),
            ends_on=timezone.localdate() - timedelta(days=5),
        )
        response = self.client.post(
            f"/api/v1/delegations/{ended_id}/cancel/",
            {"decision_reason": "Nope"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed", response.json()["detail"][0])

    def test_actions_are_hr_only(self):
        self.client.force_authenticate(user=self.dean)
        delegation_id = self._delegation()
        for action in ("approve", "reject", "cancel"):
            response = self.client.post(
                f"/api/v1/delegations/{delegation_id}/{action}/", {}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_not_supported(self):
        self.client.force_authenticate(user=self.hr_user)
        delegation_id = self._delegation()
        self.assertEqual(
            self.client.delete(f"/api/v1/delegations/{delegation_id}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class DelegationAdminTests(TestCase):
    """Delegation admin visibility guards."""

    def setUp(self):
        self.site = AdminSite()

    def test_registered_and_no_delete(self):
        admin = DelegationAdmin(Delegation, self.site)
        self.assertFalse(admin.has_delete_permission(None))

    def test_list_renders_state_and_related_people(self):
        hr = make_active_user(User.Role.HR, "hr-a@test.luanar")
        dean = make_active_user(User.Role.DEAN, "dean-a@test.luanar")
        hod = make_active_user(User.Role.HOD, "hod-a@test.luanar")
        delegation = make_delegation(
            dean,
            timezone.localdate(),
            None,
            status=Delegation.Status.APPROVED,
            delegate=hod,
        )
        admin = DelegationAdmin(Delegation, self.site)
        self.assertEqual(admin.state(delegation), "active")
        self.assertEqual(str(delegation.approver), f"{dean.get_full_name()} (dean)")


# ---------------------------------------------------------------------------
# Reassignment helpers
# ---------------------------------------------------------------------------


def make_application(
    employee,
    *,
    approver=None,
    ref=None,
    status=LeaveApplication.Status.SUBMITTED,
):
    return LeaveApplication.objects.create(
        employee=employee,
        current_approver=approver,
        status=status,
        reference_number=ref,
        start_date=timezone.localdate() + timedelta(days=7),
        end_date=timezone.localdate() + timedelta(days=14),
        calculated_days=7,
        reason="Family emergency",
        submitted_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Reassignment model tests
# ---------------------------------------------------------------------------


class ReassignmentModelTests(TestCase):
    """Reassignment model ordering and string representation."""

    def test_str_includes_reference_number_and_new_approver(self):
        employee = make_active_user(User.Role.EMPLOYEE, "emp-re01@test.luanar")
        app = make_application(employee, ref="LUANAR-2026-0001")
        hod = make_active_user(User.Role.HOD, "hod-re01@test.luanar")
        reassignment = Reassignment.objects.create(
            application=app,
            to_approver=hod,
            reason="Moved",
            decided_by=make_active_user(User.Role.HR, "hr-re01@test.luanar"),
        )
        self.assertEqual(
            str(reassignment),
            f"Reassignment(LUANAR-2026-0001 → {hod.get_full_name()})",
        )

    def test_ordering_is_newest_first(self):
        employee = make_active_user(User.Role.EMPLOYEE, "emp-re02@test.luanar")
        app = make_application(employee, ref="LUANAR-2026-0002")
        hod = make_active_user(User.Role.HOD, "hod-re02@test.luanar")
        dean = make_active_user(User.Role.DEAN, "dean-re02@test.luanar")
        hr = make_active_user(User.Role.HR, "hr-re02@test.luanar")
        first = Reassignment.objects.create(
            application=app, to_approver=hod, reason="First", decided_by=hr,
        )
        second = Reassignment.objects.create(
            application=app, to_approver=dean, reason="Second", decided_by=hr,
        )
        # ``update`` bypasses auto_now_add so we control the timestamps
        Reassignment.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        Reassignment.objects.filter(pk=second.pk).update(created_at=timezone.now())
        reassignments = list(
            Reassignment.objects.filter(application=app).select_related(
                "to_approver"
            )
        )
        self.assertEqual([r.to_approver.pk for r in reassignments], [dean.pk, hod.pk])


# ---------------------------------------------------------------------------
# Reassignment service tests
# ---------------------------------------------------------------------------


class ReassignmentServiceTests(TestCase):
    """Service-level reassignment validation."""

    def setUp(self):
        self.hr = make_active_user(User.Role.HR, "hr-svc@test.luanar")
        self.employee = make_active_user(User.Role.EMPLOYEE, "emp-svc@test.luanar")
        self.dean = make_active_user(User.Role.DEAN, "dean-svc@test.luanar")
        self.hod = make_active_user(User.Role.HOD, "hod-svc@test.luanar")

    def _submitted_app(self, approver=None):
        return make_application(self.employee, approver=approver)

    def test_happy_path_sets_current_approver_and_records_from(self):
        app = self._submitted_app()
        reassignment = reassign_application(
            application=app,
            to_approver=self.dean,
            actor=self.hr,
            reason="Dean took over",
        )
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.dean.pk)
        self.assertEqual(reassignment.from_approver_id, None)
        self.assertEqual(reassignment.to_approver_id, self.dean.pk)
        self.assertEqual(reassignment.reason, "Dean took over")
        self.assertEqual(reassignment.decided_by_id, self.hr.pk)

    def test_second_reassignment_records_previous_approver(self):
        app = self._submitted_app()
        reassign_application(
            application=app,
            to_approver=self.hod,
            actor=self.hr,
            reason="First hop",
        )
        app.refresh_from_db()
        second = reassign_application(
            application=app,
            to_approver=self.dean,
            actor=self.hr,
            reason="Second hop",
        )
        app.refresh_from_db()
        self.assertEqual(second.from_approver_id, self.hod.pk)
        self.assertEqual(app.current_approver_id, self.dean.pk)

    def test_reason_is_trimmed(self):
        app = self._submitted_app()
        reassignment = reassign_application(
            application=app,
            to_approver=self.dean,
            actor=self.hr,
            reason="  Temporary override  ",
        )
        self.assertEqual(reassignment.reason, "Temporary override")

    def test_blank_reason_rejected(self):
        app = self._submitted_app()
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="",
            )
        self.assertEqual(ctx.exception.field, "reason")
        with self.assertRaises(ReassignmentError):
            reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="   ",
            )
        app.refresh_from_db()
        self.assertIsNone(app.current_approver_id)

    def test_draft_application_rejected(self):
        draft = make_application(
            self.employee,
            status=LeaveApplication.Status.DRAFT,
            ref="DRAFT-001",
        )
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=draft,
                to_approver=self.dean,
                actor=self.hr,
                reason="Mistake",
            )
        self.assertEqual(ctx.exception.field, "application")

    def test_inactive_to_approver_rejected(self):
        app = self._submitted_app()
        inactive = User.objects.create_user(
            username="inactive@test.luanar",
            email="inactive@test.luanar",
            password=SEED_PASSWORD,
            first_name="Inactive",
            last_name="Approver",
            role=User.Role.DEAN,
            is_active=False,
        )
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=app,
                to_approver=inactive,
                actor=self.hr,
                reason="Try",
            )
        self.assertEqual(ctx.exception.field, "to_approver")

    def test_same_current_approver_rejected(self):
        app = self._submitted_app(approver=self.dean)
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="Same",
            )
        self.assertEqual(ctx.exception.field, "to_approver")
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.dean.pk)

    def test_own_applicant_rejected(self):
        app = make_application(self.dean, ref="APPLIC-001")
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="Own app",
            )
        self.assertEqual(ctx.exception.field, "to_approver")
        self.assertIn("applicant", ctx.exception.message)

    def test_error_leaves_application_unchanged(self):
        app = self._submitted_app()
        with self.assertRaises(ReassignmentError):
            reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="",
            )
        app.refresh_from_db()
        self.assertIsNone(app.current_approver_id)
        self.assertFalse(Reassignment.objects.filter(application=app).exists())


# ---------------------------------------------------------------------------
# Reassignment API tests
# ---------------------------------------------------------------------------


class ReassignmentEndpointTests(TestCase):
    """API-level reassignment create/list/retrieve and permission checks."""

    def setUp(self):
        self.client = APIClient()
        self.hr_user = User.objects.create_user(
            username="hr-api@test.luanar",
            email="hr-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            username="emp-api@test.luanar",
            email="emp-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )
        self.dean = User.objects.create_user(
            username="dean-api@test.luanar",
            email="dean-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Dean",
            role=User.Role.DEAN,
        )
        self.hod = User.objects.create_user(
            username="hod-api@test.luanar",
            email="hod-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HOD",
            role=User.Role.HOD,
        )
        self.application = make_application(self.employee_user, ref="LUANAR-2026-0010")
        self.application.submitted_at = timezone.now() - timedelta(days=10)
        self.application.save(update_fields=["submitted_at"])
        self.application_second = make_application(
            self.employee_user, ref="LUANAR-2026-0011"
        )
        self.application_second.submitted_at = timezone.now() - timedelta(days=9)
        self.application_second.save(update_fields=["submitted_at"])

    def _pending_url(self):
        return "/api/v1/reassignments/pending/"

    def _create_url(self):
        return "/api/v1/reassignments/"

    def _detail_url(self, pk):
        return f"/api/v1/reassignments/{pk}/"

    # --- Authentication / permissions ---

    def test_list_requires_authentication(self):
        for url in (self._create_url(), self._pending_url()):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_authentication(self):
        response = self.client.post(
            self._create_url(), {"application": str(self.application.id)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_requires_authentication(self):
        response = self.client.get(self._detail_url(self.application.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_user_gets_403(self):
        self.client.force_authenticate(user=self.employee_user)
        for url in (self._create_url(), self._pending_url()):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post(
            self._create_url(), {"application": str(self.application.id)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_retrieve(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(self._detail_url(self.application.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_not_supported(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.delete(self._detail_url(self.application.id))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- Pending queue ---

    def test_pending_lists_only_submitted_and_oldest_newest_first(self):
        draft = make_application(
            self.employee_user,
            status=LeaveApplication.Status.DRAFT,
            ref="DRAFT-100",
        )
        app1 = make_application(self.employee_user, ref="PEND-001")
        app1.submitted_at = timezone.now() - timedelta(days=2)
        app1.save(update_fields=["submitted_at"])
        app2 = make_application(self.employee_user, ref="PEND-002")
        app2.submitted_at = timezone.now() - timedelta(days=1)
        app2.save(update_fields=["submitted_at"])

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self._pending_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        refs = [r["reference_number"] for r in results]
        # Newest first. The setUp applications are intentionally old (time-10d /
        # time-9d); PEND-002/PEND-001 were submitted yesterday/two days ago, so
        # they lead the queue. Drafts are never shown.
        self.assertEqual(
            refs, ["PEND-002", "PEND-001", "LUANAR-2026-0011", "LUANAR-2026-0010"]
        )
        self.assertEqual(response.json()["count"], 4)

    def test_pending_object_shape(self):
        app = make_application(
            self.employee_user,
            approver=self.hod,
            ref="SHAPE-001",
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self._pending_url())
        results = response.json()["results"]
        payload = next(
            r for r in results if r["reference_number"] == "SHAPE-001"
        )
        self.assertEqual(payload["id"], str(app.id))
        self.assertEqual(payload["reference_number"], "SHAPE-001")
        self.assertEqual(payload["employee"], self.employee_user.pk)
        self.assertEqual(payload["employee_name"], self.employee_user.get_full_name())
        self.assertEqual(payload["current_approver"], self.hod.pk)
        self.assertEqual(payload["current_approver_name"], self.hod.get_full_name())
        self.assertIn("leave_type_name", payload)
        self.assertIn("start_date", payload)
        self.assertIn("reason", payload)
        self.assertIn("submitted_at", payload)

    def test_pending_current_approver_fields_when_none(self):
        make_application(self.employee_user, ref="NOAPPR-001")
        self.client.force_authenticate(user=self.hr_user)
        results = self.client.get(self._pending_url()).json()["results"]
        payload = next(
            r for r in results if r["reference_number"] == "NOAPPR-001"
        )
        self.assertIsNone(payload["current_approver"])
        self.assertEqual(payload["current_approver_name"], "")

    # --- Create (reassign) ---

    def test_create_happy_path(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "Urgent case",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["application"], str(self.application.id))
        self.assertEqual(data["to_approver"], self.dean.pk)
        self.assertEqual(data["to_approver_name"], self.dean.get_full_name())
        self.assertEqual(data["from_approver"], None)
        self.assertEqual(data["decided_by"], self.hr_user.pk)
        self.assertEqual(data["reason"], "Urgent case")
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_approver_id, self.dean.pk)

    def test_create_with_second_reassignment_shows_from_approver(self):
        self.application.current_approver = self.hod
        self.application.save(update_fields=["current_approver"])
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "Move",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["from_approver"], self.hod.pk)
        self.assertEqual(
            response.json()["from_approver_name"], self.hod.get_full_name()
        )

    def test_create_blank_reason_400(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.json())
        self.application.refresh_from_db()
        self.assertIsNone(self.application.current_approver_id)

    def test_create_draft_application_400(self):
        draft = make_application(
            self.employee_user,
            status=LeaveApplication.Status.DRAFT,
            ref="DRAFT-400",
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(draft.id),
                "to_approver": self.dean.pk,
                "reason": "Bad request",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("application", response.json())

    def test_create_same_current_approver_400(self):
        self.application.current_approver = self.dean
        self.application.save(update_fields=["current_approver"])
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "Same",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to_approver", response.json())

    def test_create_own_applicant_400(self):
        app = make_application(self.dean, ref="APPLICANT-400")
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(app.id),
                "to_approver": self.dean.pk,
                "reason": "Own",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to_approver", response.json())

    def test_create_inactive_to_approver_400(self):
        inactive = User.objects.create_user(
            username="inactive-api@test.luanar",
            email="inactive-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Inactive",
            last_name="User",
            role=User.Role.DEAN,
            is_active=False,
        )
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": inactive.pk,
                "reason": "Nope",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to_approver", response.json())

    def test_create_employee_role_to_approver_400(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.employee_user.pk,
                "reason": "No",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to_approver", response.json())

    # --- History list + ?application filter ---

    def test_history_lists_all_reassignments(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "First",
            },
            format="json",
        )
        self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.hod.pk,
                "reason": "Second",
            },
            format="json",
        )
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 2)

    def test_history_filter_by_application(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "App1 only",
            },
            format="json",
        )
        self.client.post(
            self._create_url(),
            {
                "application": str(self.application_second.id),
                "to_approver": self.hod.pk,
                "reason": "App2",
            },
            format="json",
        )
        response = self.client.get(
            self._create_url(),
            {"application": str(self.application.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["reason"], "App1 only"
        )

    # --- Retrieve ---

    def test_retrieve(self):
        self.client.force_authenticate(user=self.hr_user)
        create_resp = self.client.post(
            self._create_url(),
            {
                "application": str(self.application.id),
                "to_approver": self.dean.pk,
                "reason": "Retrieve me",
            },
            format="json",
        )
        reassignment_id = create_resp.json()["id"]
        response = self.client.get(self._detail_url(reassignment_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["reason"], "Retrieve me")
        self.assertEqual(response.json()["to_approver"], self.dean.pk)

    def test_retrieve_nonexistent_404(self):
        self.client.force_authenticate(user=self.hr_user)
        fake_id = uuid.uuid4()
        response = self.client.get(self._detail_url(fake_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Reassignment admin tests
# ---------------------------------------------------------------------------


class ReassignmentAdminTests(TestCase):
    """Reassignment admin visibility guards."""

    def setUp(self):
        self.site = AdminSite()

    def test_registered_and_no_delete(self):
        admin = ReassignmentAdmin(Reassignment, self.site)
        self.assertFalse(admin.has_delete_permission(None))

    def test_list_renders_employee_name(self):
        hr = make_active_user(User.Role.HR, "hr-admin@test.luanar")
        employee = make_active_user(User.Role.EMPLOYEE, "emp-admin@test.luanar")
        app = make_application(employee, ref="ADMIN-001")
        to_approver = make_active_user(User.Role.DEAN, "dean-admin@test.luanar")
        reassignment = Reassignment.objects.create(
            application=app, to_approver=to_approver, reason="Admin test", decided_by=hr,
        )
        admin = ReassignmentAdmin(Reassignment, self.site)
        self.assertEqual(admin.employee_name(reassignment), employee.get_full_name())