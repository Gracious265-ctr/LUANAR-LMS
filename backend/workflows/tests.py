import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.forms.models import inlineformset_factory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication
from users.models import User

from approvals.admin import (
    DelegationAdmin,
    ReassignmentAdmin,
)
from .admin import (
    SectionForm,
    SectionInline,
    SectionInlineFormSet,
    WorkflowAdmin,
    WorkflowAdminForm,
)
from .testing import (
    create_user_with_role,
    ensure_roles,
    make_approver,
    make_employee,
    make_section,
    make_stage,
    make_team,
    make_workflow,
)
from organisation.models import ApproverRole
from teams.models import Team
from .models import Section, Workflow
from approvals.models import Delegation

from approvals.models import Reassignment
from approvals.services import (
    DelegationActionError,
    ReassignmentError,
    active_delegation_for,
    approve_delegation,
    cancel_delegation,
    find_conflicting_delegation,
    open_request_exists,
    reassign_application,
    reject_delegation,
    resolve_delegate_user,
)
from organisation.services import create_team_role_assignment, is_approver_user

from .services import (
    StageSequenceError,
    missing_approver_roles,
    normalize_section_sequence,
)

SEED_PASSWORD = "testpass123"

VALID_SECTIONS = [
    {"order": 1, "name": "Supervisor", "approver_role": "supervisor"},
    {"order": 2, "name": "HOD", "approver_role": "hod"},
    {"order": 3, "name": "Registrar", "approver_role": "registrar"},
    {"order": 4, "name": "DVC", "approver_role": "dvc"},
]


def designate_manager(team: Team, hr, *, username: str | None = None):
    """HR names ``team``'s manager and returns them.

    Building and editing a chain is the manager's job after the handover: HR
    creates the team and designates the manager, and the manager owns the
    chain writes from then on. Tests of the chain endpoint therefore act as the
    designated manager rather than as HR. The ``dvc`` role is used because it
    is team-scoped (not institution-wide) and is not staffed by the team
    fixtures here, so designating it cannot collide with an existing approver.
    """
    manager = make_employee(
        username or f"manager-{team.code}@test.luanar",
        team=None,
        category=team.category,
    )
    create_team_role_assignment(
        team=team,
        role=ensure_roles("dvc")["dvc"],
        user=manager,
        actor=hr,
        is_team_manager=True,
    )
    return manager


class SectionSequenceTests(TestCase):
    """Service-level workflow section-sequence validation."""

    def setUp(self):
        ensure_roles("supervisor", "hod", "registrar", "dvc", "dean")

    def test_valid_sequence_normalizes_to_one_based_order(self):
        result = normalize_section_sequence(VALID_SECTIONS)
        self.assertEqual(
            [section["approver_role"] for section in result],
            ["supervisor", "hod", "registrar", "dvc"],
        )
        self.assertEqual([section["order"] for section in result], [1, 2, 3, 4])

    def test_empty_sequence_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_section_sequence([])
        self.assertEqual(ctx.exception.field, "sections")

    def test_unknown_approver_role_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_section_sequence([{"order": 1, "approver_role": "employee"}])
        self.assertEqual(ctx.exception.field, "approver_role")

    def test_a_repeated_approver_role_is_refused(self):
        """One position may sit at only one point in a chain (Unit 30).

        This used to be allowed: the same office could sign off at two steps, and
        only ``order`` had to be unique. A role appearing twice in one workflow
        means the same capacity deciding twice at two different points, which
        ``section_workflow_role_unique`` now refuses at the database too. The
        role may still be used by a *different* workflow.
        """
        ensure_roles("hod", "dean")
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_section_sequence(
                [
                    {"order": 1, "name": "First HOD", "approver_role": "hod"},
                    {"order": 2, "name": "Dean", "approver_role": "dean"},
                    {"order": 3, "name": "Second HOD", "approver_role": "hod"},
                ]
            )
        self.assertIn("already assigned to another stage", str(ctx.exception))

    def test_a_role_may_still_repeat_across_different_workflows(self):
        """The rule is per workflow, never global.

        Reusing a role on another team's chain is normal — the same office
        approves for more than one team — so the payload validator, which cannot
        see other workflows, must not refuse it.
        """
        result = normalize_section_sequence(
            [
                {"order": 1, "name": "HOD", "approver_role": "hod"},
                {"order": 2, "name": "Dean", "approver_role": "dean"},
            ]
        )
        self.assertEqual(
            [section["approver_role"] for section in result], ["hod", "dean"]
        )

    def test_a_blank_name_falls_back_to_the_role_label(self):
        """A saved section is never nameless; HR can still say what it is for."""
        result = normalize_section_sequence(
            [{"order": 1, "name": "   ", "approver_role": "hod"}]
        )
        self.assertEqual(result[0]["name"], "Head of Department")

    def test_non_positive_order_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_section_sequence([{"order": 0, "approver_role": "hod"}])
        self.assertEqual(ctx.exception.field, "order")

    def test_duplicate_order_rejected(self):
        with self.assertRaises(StageSequenceError) as ctx:
            normalize_section_sequence(
                [{"order": 1, "approver_role": "hod"}, {"order": 1, "approver_role": "registrar"}]
            )
        self.assertEqual(ctx.exception.field, "order")


class WorkflowEndpointTests(TestCase):
    """The chain endpoint: read what a team owns, write only what it owns.

    A team may own several chains, so each one is configured on its own here —
    create the replacement steps alongside the live one, then point the team at
    them. What survives from the old read-only contract is ownership: a chain
    belongs to the team it was created for, it cannot be adopted by another,
    and it is never scheduled or switched off on its own.

    The refusals are tested rather than assumed. An endpoint that merely went
    unused would look identical from the tests, and the first thing a future
    change would do is reach for ``POST /workflows/`` because it is right there.
    """

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
        ensure_roles("supervisor", "hod", "registrar", "dvc", "dean")

        self.workflow = Workflow.objects.create(name="Academic approval")
        Workflow.objects.create(name="Administration approval")
        for section in VALID_SECTIONS:
            make_section(
                self.workflow,
                section["order"],
                section["approver_role"],
                name=section["name"],
            )

        self.list_url = "/api/v1/workflows/"
        self.detail_url = f"/api/v1/workflows/{self.workflow.id}/"

    def test_list_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.post(self.list_url, {}).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_detail_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_non_hr_role_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_hr_can_list_workflows_ordered_by_name(self):
        """The list stays: the team screens and the audit trail need to read it."""
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data["results"]]  # type: ignore[index]
        self.assertEqual(
            names, ["Academic approval", "Administration approval"]
        )

    def test_hr_can_retrieve_workflow_with_ordered_sections(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sections = response.data["sections"]  # type: ignore[index]
        self.assertEqual(
            [section["approver_role"] for section in sections],
            ["supervisor", "hod", "registrar", "dvc"],
        )
        self.assertEqual([section["order"] for section in sections], [1, 2, 3, 4])

    def test_a_chain_cannot_be_created_without_a_team(self):
        """A standalone chain still has no team to belong to.

        A chain created on its own would be a set of steps nothing routes
        through and nobody could say whose approval they are. So the endpoint
        takes a team on create, and refuses anything else.
        """
        team = make_team("Dean office", ["dean"], campus="Main Campus")
        manager = designate_manager(team, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            self.list_url,
            {
                "name": "Dean office approval",
                "sections": [
                    {"order": 1, "name": "HOD", "approver_role": "hod"},
                    {"order": 2, "name": "Dean", "approver_role": "dean"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data)
        self.assertFalse(Workflow.objects.filter(name="Dean office approval").exists())

    def test_manager_can_create_a_workflow_for_a_team(self):
        """A team may own several chains, and each is configured separately.

        This is the replacement chain case: build the new steps alongside the
        live one, then point the team at it when it is ready. The chain is owned
        by the team it is created for, which is what makes it editable here.
        """
        team = make_team("Dean office", ["hod", "dean"], campus="Main Campus")
        manager = designate_manager(team, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            self.list_url,
            {
                "name": f"{team.name} replacement",
                "team": team.pk,
                "sections": [
                    {"order": 1, "name": "HOD", "approver_role": "hod"},
                    {"order": 2, "name": "Dean", "approver_role": "dean"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        workflow = Workflow.objects.get(pk=response.data["id"])
        self.assertEqual(workflow.team_id, team.pk)
        self.assertEqual(
            [s.approver_role.code for s in workflow.sections.order_by("order")],
            ["hod", "dean"],
        )

    def test_manager_can_edit_the_steps_of_a_workflow_the_team_owns(self):
        """The team's workflow screen writes here, so a write has to work.

        The rule that survives the change is ownership: the manager edits the
        chain the named team owns, not a chain that belongs to somebody else.
        """
        team = make_team("Dean office", ["hod", "dean"], campus="Main Campus")
        workflow = make_workflow(f"{team.name} workflow", ["hod", "dean"])
        workflow.team = team
        workflow.save(update_fields=["team"])
        manager = designate_manager(team, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.patch(
            f"/api/v1/workflows/{workflow.pk}/",
            {
                "sections": [
                    {"order": 1, "name": "Dean", "approver_role": "dean"},
                    {"order": 2, "name": "Registrar", "approver_role": "registrar"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        workflow.refresh_from_db()
        self.assertEqual(
            [s.approver_role.code for s in workflow.sections.order_by("order")],
            ["dean", "registrar"],
        )

    def test_a_chain_cannot_be_moved_to_another_team(self):
        """The team named at create is the team it stays with.

        A chain that could be re-pointed would re-route one team's applications
        into another team's steps, and every application already inside it would
        be stranded at a step nobody staffs for them.
        """
        owner = make_team("Dean office", ["hod", "dean"], campus="Main Campus")
        other = make_team("Registry office", ["registrar"], campus="Main Campus")
        workflow = make_workflow(f"{owner.name} workflow", ["hod", "dean"])
        workflow.team = owner
        workflow.save(update_fields=["team"])
        manager = designate_manager(owner, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.patch(
            f"/api/v1/workflows/{workflow.pk}/", {"team": other.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data)
        workflow.refresh_from_db()
        self.assertEqual(workflow.team_id, owner.pk)

    def test_an_edit_may_restate_its_own_team(self):
        """The workflow form repeats the team it edits under, which is fine.

        Sending the owning team alongside an edit names the workflow's owner
        rather than trying to move it; the refusal exists for a *different*
        team, and the edit form would otherwise be refused on every save.
        """
        owner = make_team("Dean office", ["hod", "dean"], campus="Main Campus")
        workflow = owner.workflows.first()
        manager = designate_manager(owner, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.patch(
            f"/api/v1/workflows/{workflow.pk}/",
            {"team": owner.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        workflow.refresh_from_db()
        self.assertEqual(workflow.team_id, owner.pk)

    def test_the_list_can_be_filtered_to_one_teams_workflows(self):
        """How the team screen finds every chain a team owns."""
        owner = make_team("Dean office", ["hod", "dean"], campus="Main Campus")
        make_team("Registry office", ["registrar"], campus="Main Campus")
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url, {"team": owner.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]  # type: ignore[index]
        self.assertEqual(ids, [owner.workflows.first().id])

    def test_delete_not_supported(self):
        """A chain is retired with the team, and never on its own.

        DELETE would leave the team still pointing at a chain that no longer
        exists, which is the one state this whole design is built to avoid.
        """
        self.client.force_authenticate(user=self.hr_user)
        self.assertEqual(
            self.client.delete(self.detail_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )


class WorkflowAdminTests(TestCase):
    """Workflow admin guards for stage sequences."""

    def setUp(self):
        self.workflow = Workflow.objects.create(name="Admin workflow")
        self.site = AdminSite()

    def test_section_order_must_be_at_least_one(self):
        SectionInlineForm = inlineformset_factory(
            Workflow,
            Section,
            form=SectionForm,
            formset=SectionInlineFormSet,
            fields=["order", "name", "approver_role"],
            extra=1,
        )
        formset = SectionInlineForm(
            data={
                "sections-TOTAL_FORMS": "1",
                "sections-INITIAL_FORMS": "0",
                "sections-MIN_NUM_FORMS": "1",
                "sections-MAX_NUM_FORMS": "1000",
                "sections-0-order": "0",
                "sections-0-name": "HOD",
                "sections-0-approver_role": "hod",
            },
            instance=Workflow(),
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("order", formset.errors[0])

    def test_a_repeated_approver_role_is_refused_in_the_admin(self):
        """The admin must agree with the API about what a workflow is (Unit 30).

        No admin-side rule was added for this: ``section_workflow_role_unique`` is
        a model constraint, so Django's cross-form ``validate_unique`` reports the
        repeat on the ``approver_role`` field. This test pins that, so a future
        change cannot leave the admin hitting a database error instead.
        """
        ensure_roles("hod")
        SectionInlineForm = inlineformset_factory(
            Workflow,
            Section,
            form=SectionForm,
            formset=SectionInlineFormSet,
            fields=["order", "name", "approver_role"],
            extra=1,
        )
        formset = SectionInlineForm(
            data={
                "sections-TOTAL_FORMS": "2",
                "sections-INITIAL_FORMS": "0",
                "sections-MIN_NUM_FORMS": "1",
                "sections-MAX_NUM_FORMS": "1000",
                "sections-0-order": "1",
                "sections-0-name": "First HOD",
                "sections-0-approver_role": "hod",
                "sections-1-order": "2",
                "sections-1-name": "Second HOD",
                "sections-1-approver_role": "hod",
            },
            instance=Workflow(),
        )
        self.assertFalse(formset.is_valid())
        self.assertIn(
            "duplicate", str(formset.non_form_errors()).lower()
        )
        self.assertIn("approver_role", str(formset.non_form_errors()))

    def test_duplicate_section_order_is_rejected(self):
        """Repetition is fine for a role, but two steps cannot share a position."""
        ensure_roles("hod", "dean")
        SectionInlineForm = inlineformset_factory(
            Workflow,
            Section,
            form=SectionForm,
            formset=SectionInlineFormSet,
            fields=["order", "name", "approver_role"],
            extra=1,
        )
        formset = SectionInlineForm(
            data={
                "sections-TOTAL_FORMS": "2",
                "sections-INITIAL_FORMS": "0",
                "sections-MIN_NUM_FORMS": "1",
                "sections-MAX_NUM_FORMS": "1000",
                "sections-0-order": "1",
                "sections-0-name": "One",
                "sections-0-approver_role": "hod",
                "sections-1-order": "1",
                "sections-1-name": "Two",
                "sections-1-approver_role": "dean",
            },
            instance=Workflow(),
        )
        self.assertFalse(formset.is_valid())

    def test_admin_list_prefetches_sections_for_summary(self):
        make_section(self.workflow, 1, "hod")
        second = Workflow.objects.create(name="Second")
        make_section(second, 1, "dean")
        admin = WorkflowAdmin(Workflow, self.site)
        # workflows + sections + roles: the roles come from the joined prefetch,
        # so the count is flat in the number of workflows and sections.
        with self.assertNumQueries(3):
            summaries = {
                obj.pk: admin.section_summary(obj) for obj in admin.get_queryset(None)
            }
        self.assertEqual(summaries[self.workflow.pk], "Head of Department")
        self.assertEqual(summaries[second.pk], "Dean")


def make_active_user(role, username: str) -> User:
    """An active account holding ``role``.

    ``role`` may be a :class:`~users.models.User.Role` value or an approver role
    code. An approver code also creates the role row and an institution-wide
    holding, because setting the user row alone no longer makes somebody an
    approver — see :func:`workflows.services.is_approver_user`.
    """
    return create_user_with_role(
        username,
        role=role,
        password=SEED_PASSWORD,
        first_name="Test",
        last_name="Approver",
    )


class WorkflowActivationServiceTests(TestCase):
    """Deactivated approver roles, which is the one chain-level activation check.

    The other check that used to live here — "does another active workflow
    already cover this scope?" — went away with shared chains. It existed
    because two chains could apply to the same people, so which one governed an
    applicant was ambiguous. Now every chain belongs to one team and routing
    follows the team, so two chains over the same people is a reorganisation, not a
    conflict. That question is answered by the team activation check, which can
    see both teams and report the overlap as something HR has to confirm.
    """

    def test_missing_approver_roles_lists_deactivated_roles(self):
        """Only a *deactivated* role blocks activation.

        Whether a team actually has somebody holding an active role is resolved
        per applicant at submission time, not at configuration time.
        """
        ensure_roles("dean", "supervisor")
        ApproverRole.objects.filter(code="supervisor").update(is_active=False)
        sections = [
            {"order": 1, "name": "Dean", "approver_role": "dean"},
            {"order": 2, "name": "Supervisor", "approver_role": "supervisor"},
        ]
        self.assertEqual(missing_approver_roles(sections), ["Supervisor"])

    def test_missing_approver_roles_ignores_an_unstaffed_active_role(self):
        ensure_roles("supervisor")
        self.assertEqual(
            missing_approver_roles([{"order": 1, "name": "S", "approver_role": "supervisor"}]), []
        )

    def test_missing_approver_roles_ignores_an_inactive_holder(self):
        user = make_active_user("supervisor", "supervisor@test.luanar")
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(
            missing_approver_roles([{"order": 1, "name": "S", "approver_role": "supervisor"}]), []
        )

    def test_a_role_repeated_across_steps_is_reported_once(self):
        ensure_roles("hod")
        ApproverRole.objects.filter(code="hod").update(is_active=False)
        sections = [
            {"order": 1, "name": "First HOD", "approver_role": "hod"},
            {"order": 2, "name": "Second HOD", "approver_role": "hod"},
        ]
        self.assertEqual(missing_approver_roles(sections), ["Head of Department"])


class WorkflowActivationEndpointTests(TestCase):
    """A chain has no activation of its own, because it has no life of its own.

    Scheduling a chain, putting it into force, and taking it out were all things
    HR did to a *workflow*. They are things HR now does to a *team*, and the
    team's readiness check is what answers them. So the questions these tests
    used to ask of ``POST /workflows/`` — when does this start, does it clash
    with anything, can it be switched off — are asked of the team endpoint in
    ``tests_team_configuration.py``, and what is left here is that a write here
    which tries to answer them on a chain's own behalf is still refused.
    """

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
        self.client.force_authenticate(user=self.hr_user)
        self.list_url = "/api/v1/workflows/"

    def test_a_chain_cannot_be_scheduled(self):
        """A date on a chain used to mean "this starts applying on that day".

        A chain that is not yet applying is a team that has not been activated.
        Letting the two be set independently is how you get a chain that says it
        starts in June while the team routing through it went live in May — so
        the field is named and refused rather than silently dropped.
        """
        team = make_team("Dean office", ["dean"], campus="Main Campus")
        manager = designate_manager(team, self.hr_user)
        future = (timezone.localdate() + timedelta(days=30)).isoformat()
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            self.list_url,
            {
                "name": "Workflow",
                "team": team.pk,
                "effective_from": future,
                "is_active": True,
                "sections": [{"order": 1, "name": "Dean", "approver_role": "dean"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effective_from", response.data)
        self.assertFalse(Workflow.objects.filter(name="Workflow").exists())

    def test_a_chain_cannot_be_switched_off(self):
        """Retiring is a team decision, and it is audited as one.

        Switching off a chain here would stop the team's routing at once,
        without the team's status changing and so without anything in the
        team's history saying why.
        """
        team = make_team("Dean office", ["dean"], campus="Main Campus")
        workflow = team.workflows.first()
        manager = designate_manager(team, self.hr_user)
        self.client.force_authenticate(user=manager)
        response = self.client.patch(
            f"/api/v1/workflows/{workflow.pk}/", {"is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_active", response.data)
        workflow.refresh_from_db()
        self.assertTrue(workflow.is_active)

    def test_a_chain_cannot_be_built_on_a_deactivated_role(self):
        """The role check is not bypassed by writing a chain of its own.

        Creating a step whose role is switched off is refused here just as it is
        on the team endpoint — a deactivated role is deactivated wherever it is
        named — so there is no way to produce a chain the team activation check
        would then have to reject.
        """
        team = make_team("Dean office", [], campus="Main Campus")
        manager = designate_manager(team, self.hr_user)
        # Deactivated *after* the team is built: the fixture helper creates the
        # six roles and reactivates them, which would undo the very switch this
        # test is about.
        ensure_roles("dean")
        ApproverRole.objects.filter(code="dean").update(is_active=False)
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            self.list_url,
            {
                "name": "Dead step",
                "team": team.pk,
                "sections": [{"order": 1, "name": "Dean", "approver_role": "dean"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sections", response.data)
        self.assertFalse(Workflow.objects.filter(name="Dead step").exists())

    def test_two_teams_may_own_chains_over_the_same_scope(self):
        """Two chains covering one scope is not an error any more.

        Two teams serving the same people is exactly two chains over one scope,
        and the team activation check surfaces that for HR to confirm rather
        than a shared registry refusing to be written.
        """
        first_team = make_team("Dean office", [], campus="Main Campus")
        second_team = make_team("Registry office", [], campus="Main Campus")
        first_manager = designate_manager(first_team, self.hr_user)
        second_manager = designate_manager(second_team, self.hr_user)
        self.client.force_authenticate(user=first_manager)
        first = self.client.post(
            self.list_url,
            {
                "name": "First",
                "team": first_team.pk,
                "sections": [{"order": 1, "name": "Dean", "approver_role": "dean"}],
            },
            format="json",
        )
        self.client.force_authenticate(user=second_manager)
        second = self.client.post(
            self.list_url,
            {
                "name": "Second",
                "team": second_team.pk,
                "sections": [{"order": 1, "name": "Dean", "approver_role": "dean"}],
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)


class WorkflowActivationAdminTests(TestCase):
    """The chain admin is an inspector, not a second editor.

    The form still exists because the section inline needs it, but it no longer
    validates a lifecycle: a chain cannot be scheduled or activated here,
    because that decision belongs to the team. These tests pin that the admin
    has not quietly become a way to set a chain's dates behind the team's back.
    """

    def setUp(self):
        self.site = AdminSite()
        self.today = timezone.localdate()

    def _form(self, workflow: Workflow, **overrides) -> WorkflowAdminForm:
        data = {
            "name": workflow.name,
            "effective_from": "",
            "is_active": False,
        }
        data.update(overrides)
        return WorkflowAdminForm(data=data, instance=workflow)

    def test_the_admin_refuses_to_add_a_chain(self):
        """A chain with no team is a chain nothing routes through."""
        admin = WorkflowAdmin(Workflow, self.site)
        self.assertFalse(admin.has_add_permission(None))
        self.assertFalse(admin.has_change_permission(None))

    def test_the_admin_refuses_to_delete_a_chain(self):
        """PROTECTed by the team, and the audit trail is the record of why."""
        admin = WorkflowAdmin(Workflow, self.site)
        self.assertFalse(admin.has_delete_permission(None))

    def test_the_form_still_keeps_the_fields_the_inspector_shows(self):
        """Read-only is enforced by permissions, not by removing the columns.

        Dropping the fields would make the list page lie about what a chain
        carries; refusing the write is what actually stops the edit.
        """
        workflow = Workflow.objects.create(name="Readable workflow")
        make_stage(workflow, 1, "dean")
        self.assertTrue(self._form(workflow).is_valid())


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

    def setUp(self):
        self.hr = make_active_user(User.Role.HR, "hr-deleg@test.luanar")
        self.dean = make_active_user("dean", "dean-deleg@test.luanar")
        self.hod = make_active_user("hod", "hod-deleg@test.luanar")
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

    def setUp(self):
        self.hr = make_active_user(User.Role.HR, "hr-svc@test.luanar")
        self.dean = make_active_user("dean", "dean-svc@test.luanar")
        self.hod = make_active_user("hod", "hod-svc@test.luanar")
        self.employee = make_active_user(
            User.Role.EMPLOYEE, "employee-svc@test.luanar"
        )
        self.today = timezone.localdate()

    def test_is_approver_user(self):
        self.assertTrue(is_approver_user(self.dean))
        self.assertFalse(is_approver_user(self.employee))
        self.assertFalse(is_approver_user(None))

    def test_hr_is_not_an_approver_user(self):
        """HR is admitted by an explicit check, not by holding a role.

        HR needs the delegation flow, but HR does not sit in an approval chain,
        so ``is_approver_user`` must stay False for them — otherwise HR would
        show up as a candidate approver in every team's routing.
        """
        self.assertFalse(is_approver_user(self.hr))

    def test_deactivating_a_role_retires_approver_status(self):
        role = ensure_roles("dean")["dean"]
        self.assertTrue(is_approver_user(self.dean))
        role.is_active = False
        role.save(update_fields=["is_active"])
        self.assertFalse(is_approver_user(self.dean))

    def test_inactive_user_is_never_an_approver(self):
        self.dean.is_active = False
        self.dean.save(update_fields=["is_active"])
        self.assertFalse(is_approver_user(self.dean))

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

    def test_approve_stale_requested_instance_is_rechecked_under_lock(self):
        delegation = make_delegation(self.dean, self.today)
        stale = Delegation.objects.get(pk=delegation.pk)
        delegation.status = Delegation.Status.APPROVED
        delegation.delegate = self.hod
        delegation.save(update_fields=["status", "delegate"])
        with self.assertRaises(DelegationActionError) as ctx:
            approve_delegation(
                stale, self.hr, {"delegate": self.hod, "decision_reason": "Too late"}
            )
        self.assertEqual(ctx.exception.field, "detail")
        refresh = Delegation.objects.get(pk=delegation.pk)
        self.assertEqual(refresh.status, Delegation.Status.APPROVED)
        self.assertEqual(refresh.decided_by_id, None)

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


class DelegationConcurrencyTests(TestCase):
    """Every decision re-validates under the approver lock, not just approve.

    ``approve`` was the only action that re-read the row under
    ``select_for_update``; ``reject`` and ``cancel`` trusted the caller's copy.
    These pin the re-check that makes a stale in-memory instance harmless.
    """

    def setUp(self):
        self.hr = make_active_user(User.Role.HR, "hr-conc@test.luanar")
        self.dean = make_active_user("dean", "dean-conc@test.luanar")
        self.hod = make_active_user("hod", "hod-conc@test.luanar")
        self.today = timezone.localdate()

    def test_reject_rechecks_a_stale_instance_under_lock(self):
        delegation = make_delegation(self.dean, self.today)
        stale = Delegation.objects.get(pk=delegation.pk)
        reject_delegation(delegation, self.hr, {"decision_reason": "First"})

        with self.assertRaises(DelegationActionError) as ctx:
            reject_delegation(stale, self.hr, {"decision_reason": "Second"})
        self.assertEqual(ctx.exception.field, "detail")
        fresh = Delegation.objects.get(pk=delegation.pk)
        self.assertEqual(fresh.decision_reason, "First")

    def test_cancel_rechecks_a_stale_instance_under_lock(self):
        delegation = make_delegation(
            self.dean,
            self.today,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        stale = Delegation.objects.get(pk=delegation.pk)
        cancel_delegation(delegation, self.hr, {"decision_reason": "First"})

        with self.assertRaises(DelegationActionError) as ctx:
            cancel_delegation(stale, self.hr, {"decision_reason": "Second"})
        self.assertEqual(ctx.exception.field, "detail")
        fresh = Delegation.objects.get(pk=delegation.pk)
        self.assertEqual(fresh.decision_reason, "First")

    def test_cancel_rechecks_a_delegation_that_ended_under_lock(self):
        delegation = make_delegation(
            self.dean,
            self.today,
            ends_on=self.today,
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        stale = Delegation.objects.get(pk=delegation.pk)
        # The period lapses between the caller's read and the lock. Patching the
        # clock is the only way to age a row the constraint would otherwise
        # forbid (ends_on may never precede starts_on).
        with mock.patch(
            "workflows.services.timezone.localdate",
            return_value=self.today + timedelta(days=1),
        ):
            with self.assertRaises(DelegationActionError) as ctx:
                cancel_delegation(stale, self.hr, {"decision_reason": "Too late"})
        self.assertIn("completed", ctx.exception.message)
        self.assertEqual(
            Delegation.objects.get(pk=delegation.pk).status,
            Delegation.Status.APPROVED,
        )

    def test_approve_rechecks_an_overlap_that_appeared_under_lock(self):
        """The pre-check is a fast path; the locked re-check is authoritative."""
        delegation = make_delegation(self.dean, self.today)
        approved = make_delegation(
            self.dean,
            self.today + timedelta(days=2),
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
        )
        # Slip an approved overlapping row in after the pre-check has run.
        original = find_conflicting_delegation

        def racing_conflict(*args, **kwargs):
            Delegation.objects.filter(pk=approved.pk).update(
                starts_on=self.today, ends_on=None
            )
            return original(*args, **kwargs)

        with mock.patch(
            "approvals.services.find_conflicting_delegation",
            side_effect=racing_conflict,
        ):
            with self.assertRaises(DelegationActionError) as ctx:
                approve_delegation(
                    delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
                )
        self.assertEqual(ctx.exception.field, "detail")
        self.assertIn("overlaps", ctx.exception.message)
        self.assertEqual(
            Delegation.objects.get(pk=delegation.pk).status,
            Delegation.Status.REQUESTED,
        )

    def test_approve_locks_the_approver_row_before_the_delegation(self):
        """A consistent lock order is what keeps two decisions from deadlocking."""
        delegation = make_delegation(self.dean, self.today)
        order: list[str] = []
        real_user_lock = User.objects.select_for_update
        real_delegation_lock = Delegation.objects.select_for_update

        with mock.patch.object(
            User.objects,
            "select_for_update",
            side_effect=lambda *a, **k: (
                order.append("approver") or real_user_lock(*a, **k)
            ),
        ), mock.patch.object(
            Delegation.objects,
            "select_for_update",
            side_effect=lambda *a, **k: (
                order.append("delegation") or real_delegation_lock(*a, **k)
            ),
        ):
            approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
            )

        self.assertEqual(order, ["approver", "delegation"])


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
        self.dean = create_user_with_role(
            username="dean@test.luanar",
            email="dean@test.luanar",
            password=SEED_PASSWORD,
            first_name="Dean",
            last_name="Dept",
            role="dean",
        )
        self.hod = create_user_with_role(
            username="hod@test.luanar",
            email="hod@test.luanar",
            password=SEED_PASSWORD,
            first_name="Hod",
            last_name="Head",
            role="hod",
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

    def test_list_and_retrieve_are_scoped_to_the_approver(self):
        mine = self._delegation()
        other_approver = create_user_with_role(
            username="registrar@test.luanar",
            email="registrar@test.luanar",
            password=SEED_PASSWORD,
            first_name="Reg",
            last_name="Registrar",
            role="registrar",
        )
        theirs = make_delegation(
            other_approver, timezone.localdate(), delegate=self.hod
        ).pk
        # An approver sees the delegations they are a party to...
        self.client.force_authenticate(user=self.dean)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], mine)
        self.assertEqual(
            self.client.get(f"/api/v1/delegations/{mine}/").status_code,
            status.HTTP_200_OK,
        )
        # ...but somebody else's is a 404, not a 403 that would confirm it exists.
        self.assertEqual(
            self.client.get(f"/api/v1/delegations/{theirs}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        # HR still sees everything.
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 2)

    def test_list_denies_a_plain_employee(self):
        self._delegation()
        self.client.force_authenticate(user=self.employee)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_candidates_lists_active_approvers_excluding_self(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get("/api/v1/delegations/candidates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["candidates"]
        names = {row["id"] for row in rows}
        self.assertNotIn(self.dean.id, names)
        self.assertIn(self.hod.id, names)
        self.assertNotIn(self.employee.id, names)
        for row in rows:
            self.assertEqual(set(row), {"id", "full_name", "role"})

    def test_candidates_denies_a_plain_employee(self):
        self.client.force_authenticate(user=self.employee)
        self.assertEqual(
            self.client.get("/api/v1/delegations/candidates/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_one_open_request_per_approver_is_enforced_by_the_database(self):
        """The service check is a bare EXISTS; the partial unique index is the
        backstop that makes two concurrent requests for one approver impossible."""
        self._delegation()
        with self.assertRaises(IntegrityError):
            # Nested atomic = savepoint, so the test transaction survives.
            with transaction.atomic():
                make_delegation(self.dean, timezone.localdate())

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
        dean = make_active_user("dean", "dean-a@test.luanar")
        hod = make_active_user("hod", "hod-a@test.luanar")
        delegation = make_delegation(
            dean,
            timezone.localdate(),
            None,
            status=Delegation.Status.APPROVED,
            delegate=hod,
        )
        admin = DelegationAdmin(Delegation, self.site)
        self.assertEqual(admin.state(delegation), "active")
        # ``User.__str__`` now shows the system role, so the position comes from
        # the role graph via the admin's own column.
        self.assertEqual(
            str(delegation.approver), f"{dean.get_full_name()} (approver)"
        )
        self.assertEqual(admin.approver_roles(delegation), "dean")


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
        hod = make_active_user("hod", "hod-re01@test.luanar")
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
        hod = make_active_user("hod", "hod-re02@test.luanar")
        dean = make_active_user("dean", "dean-re02@test.luanar")
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
        self.dean = make_active_user("dean", "dean-svc@test.luanar")
        self.hod = make_active_user("hod", "hod-svc@test.luanar")

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

    def test_request_stale_submitted_instance_is_rechecked_under_lock(self):
        app = self._submitted_app()
        stale = LeaveApplication.objects.get(pk=app.pk)
        app.status = LeaveApplication.Status.DRAFT
        app.save(update_fields=["status"])
        with self.assertRaises(ReassignmentError) as ctx:
            reassign_application(
                application=stale,
                to_approver=self.dean,
                actor=self.hr,
                reason="Too late",
            )
        self.assertEqual(ctx.exception.field, "application")
        refresh = LeaveApplication.objects.get(pk=app.pk)
        self.assertEqual(refresh.current_approver_id, None)
        self.assertFalse(Reassignment.objects.filter(application=app).exists())

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
        inactive = create_user_with_role(
            username="inactive@test.luanar",
            email="inactive@test.luanar",
            password=SEED_PASSWORD,
            first_name="Inactive",
            last_name="Approver",
            role="dean",
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
        self.dean = create_user_with_role(
            username="dean-api@test.luanar",
            email="dean-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="Dean",
            role="dean",
        )
        self.hod = create_user_with_role(
            username="hod-api@test.luanar",
            email="hod-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Test",
            last_name="HOD",
            role="hod",
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

    def test_pending_reports_the_acting_approver_when_cover_is_active(self):
        """HR must see who actually holds the application, not only the spine.

        Reassigning an application to an approver who is themselves away moves
        ``current_approver`` without changing who acts, so a queue that reported
        only the responsible approver would read as a successful intervention
        that quietly did nothing.
        """
        app = make_application(
            self.employee_user, approver=self.dean, ref="DELEG-001"
        )
        Delegation.objects.create(
            approver=self.dean,
            delegate=self.hod,
            starts_on=timezone.localdate(),
            ends_on=timezone.localdate() + timedelta(days=30),
            requested_by=self.dean,
            status=Delegation.Status.APPROVED,
        )
        self.client.force_authenticate(user=self.hr_user)
        results = self.client.get(self._pending_url()).json()["results"]
        payload = next(r for r in results if r["reference_number"] == "DELEG-001")

        self.assertEqual(payload["current_approver"], self.dean.pk)
        self.assertEqual(payload["acting_approver"], self.hod.pk)
        self.assertEqual(
            payload["acting_approver_name"], self.hod.get_full_name()
        )
        self.assertTrue(payload["is_delegated"])

    def test_pending_reports_the_responsible_approver_when_no_cover(self):
        make_application(self.employee_user, approver=self.dean, ref="NOCOV-001")
        self.client.force_authenticate(user=self.hr_user)
        results = self.client.get(self._pending_url()).json()["results"]
        payload = next(r for r in results if r["reference_number"] == "NOCOV-001")

        self.assertEqual(payload["acting_approver"], self.dean.pk)
        self.assertEqual(payload["acting_approver_name"], self.dean.get_full_name())
        self.assertFalse(payload["is_delegated"])

    def test_pending_ignores_cover_that_has_not_started_or_has_ended(self):
        make_application(self.employee_user, approver=self.dean, ref="WINDOW-001")
        today = timezone.localdate()
        for label, starts_on, ends_on in (
            ("future", today + timedelta(days=5), today + timedelta(days=30)),
            ("ended", today - timedelta(days=30), today - timedelta(days=1)),
        ):
            Delegation.objects.create(
                approver=self.dean,
                delegate=self.hod,
                starts_on=starts_on,
                ends_on=ends_on,
                requested_by=self.dean,
                status=Delegation.Status.APPROVED,
            )
        self.client.force_authenticate(user=self.hr_user)
        results = self.client.get(self._pending_url()).json()["results"]
        payload = next(r for r in results if r["reference_number"] == "WINDOW-001")

        self.assertEqual(payload["acting_approver"], self.dean.pk)
        self.assertFalse(payload["is_delegated"])

    def test_pending_acting_approver_is_none_when_unassigned(self):
        make_application(self.employee_user, ref="NONEACT-001")
        self.client.force_authenticate(user=self.hr_user)
        results = self.client.get(self._pending_url()).json()["results"]
        payload = next(r for r in results if r["reference_number"] == "NONEACT-001")

        self.assertIsNone(payload["acting_approver"])
        self.assertEqual(payload["acting_approver_name"], "")
        self.assertFalse(payload["is_delegated"])

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
        inactive = create_user_with_role(
            username="inactive-api@test.luanar",
            email="inactive-api@test.luanar",
            password=SEED_PASSWORD,
            first_name="Inactive",
            last_name="User",
            role="dean",
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

    def test_invalid_application_filter_returns_400_not_500(self):
        self.client.force_authenticate(user=self.hr_user)
        for bad in ("not-a-uuid", "123", "zzz"):
            response = self.client.get(self._create_url(), {"application": bad})
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, f"application={bad}"
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
        to_approver = make_active_user("dean", "dean-admin@test.luanar")
        reassignment = Reassignment.objects.create(
            application=app, to_approver=to_approver, reason="Admin test", decided_by=hr,
        )
        admin = ReassignmentAdmin(Reassignment, self.site)
        self.assertEqual(admin.employee_name(reassignment), employee.get_full_name())

class WorkflowSerializerAtomicityTests(TestCase):
    """A failed audit write leaves no half-written chain behind.

    A chain and its steps are written in one transaction. If the audit write
    fails, the whole thing goes: a chain whose steps exist but whose creation
    was never recorded is exactly the state nobody can explain later.
    """

    def setUp(self):
        from rest_framework.test import APIRequestFactory

        self.hr = User.objects.create_user(
            username="wf-atomic@test.luanar",
            email="wf-atomic@test.luanar",
            password=SEED_PASSWORD,
            role=User.Role.HR,
        )
        request = APIRequestFactory().post("/")
        request.user = self.hr
        self.request = request
        ensure_roles("supervisor", "hod")
        # A team the manager owns. Its own step is staffed by somebody else, so
        # the person reused to staff the chain these tests write is a team member
        # with no chain of their own yet.
        self.team = make_team("Atomic rollback team", ["hod"])
        self.manager = designate_manager(self.team, self.hr)
        self.approver = make_approver(
            "hod",
            username="hod-atomic@test.luanar",
            institution_wide=False,
            team=self.team,
        )
        self.chain_payload = {
            "team": self.team.pk,
            "name": "Atomic rollback chain",
            "sections": [
                {
                    "name": "HOD",
                    "approver_role": "hod",
                    "approver": self.approver.pk,
                }
            ],
        }

    def _serializer(self, *args, **kwargs):
        from .serializers import WorkflowWriteSerializer

        return WorkflowWriteSerializer(
            *args, context={"request": self.request, "actor": self.manager}, **kwargs
        )

    def test_create_rolls_back_the_chain_and_its_steps(self):
        serializer = self._serializer(data=self.chain_payload)
        serializer.is_valid(raise_exception=True)
        with mock.patch(
            "workflows.services.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                serializer.save()
        self.assertFalse(Workflow.objects.filter(name="Atomic rollback chain").exists())
        self.assertEqual(
            Section.objects.filter(workflow__name="Atomic rollback chain").count(), 0
        )

    def test_a_chain_edit_rolls_back_its_rewrite(self):
        """An edit that cannot be recorded does not half-apply.

        A chain rewritten but not audited would be steps somebody changed and
        nobody can say when or why, which is worse than the edit being refused.
        """
        serializer = self._serializer(data=self.chain_payload)
        serializer.is_valid(raise_exception=True)
        workflow = serializer.save()

        edit = self._serializer(
            workflow,
            data={
                "sections": [{"name": "Only step", "approver_role": "supervisor"}]
            },
            partial=True,
        )
        edit.is_valid(raise_exception=True)
        with mock.patch(
            "workflows.services.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                edit.save()

        workflow.refresh_from_db()
        self.assertEqual(workflow.sections.count(), 1)
        self.assertEqual(workflow.sections.get().name, "HOD")


class SpineIntegrityTests(TestCase):
    """Delegation and reassignment history rows are protected, not dropped."""

    def setUp(self):
        self.hr = make_active_user(User.Role.HR, "hr-spine@test.luanar")
        self.dean = make_active_user("dean", "dean-spine@test.luanar")
        self.hod = make_active_user("hod", "hod-spine@test.luanar")
        self.employee = make_active_user(
            User.Role.EMPLOYEE, "emp-spine@test.luanar"
        )
        self.app = make_application(self.employee, ref="LUANAR-2026-SPINE")

    def test_approver_with_delegation_cannot_be_deleted(self):
        from django.db.models.deletion import ProtectedError

        make_delegation(self.dean, timezone.localdate())
        with self.assertRaises(ProtectedError):
            self.dean.delete()
        self.assertTrue(User.objects.filter(pk=self.dean.pk).exists())

    def test_replaced_approver_in_reassignment_cannot_be_deleted(self):
        from django.db.models.deletion import ProtectedError

        Reassignment.objects.create(
            application=self.app,
            from_approver=self.dean,
            to_approver=self.hod,
            reason="Coverage",
            decided_by=self.hr,
        )
        with self.assertRaises(ProtectedError):
            self.dean.delete()

    def test_application_with_reassignment_cannot_be_deleted(self):
        from django.db.models.deletion import ProtectedError

        Reassignment.objects.create(
            application=self.app,
            to_approver=self.hod,
            reason="Coverage",
            decided_by=self.hr,
        )
        with self.assertRaises(ProtectedError):
            self.app.delete()
        self.assertTrue(LeaveApplication.objects.filter(pk=self.app.pk).exists())
from workflows.testing import create_user_with_role, make_section, make_stage
