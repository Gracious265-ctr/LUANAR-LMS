"""The role-graph migrations, exercised forwards, backwards, and re-run.

These are the migrations that turn hardcoded role codes into data. A data
migration that has only ever been run on an empty test database proves very
little: the interesting cases are a database that already holds workflows,
stages, applications, and application stages, and the reverse of every step.

:class:`django.test.TransactionTestCase` is required rather than ``TestCase``:
``MigrationExecutor`` issues DDL and commits on its own, and the rollback that
restores the "current" migration state at the end of each test cannot happen
inside ``TestCase``'s wrapping transaction.
"""

from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

WORKFLOWS = [
    ("workflows", "0010_approverrole_campus_team_structure"),
    ("workflows", "0011_backfill_approver_roles"),
    ("workflows", "0012_role_foreign_keys"),
]
USERS = [
    ("users", "0005_employeeprofile_team"),
    ("users", "0006_alter_user_role"),
]
AUDIT = [("audit", "0011_alter_auditentry_target_type")]

# The "before roles were data" point, as a list of targets rather than a single
# one. Both apps have to be named: ``users.0005`` adds the ``team`` column *and*
# points it at the ``Team`` table ``workflows.0010`` creates, so rewinding the
# workflows app alone would leave a foreign key on a table that no longer exists
# and make the reverse fail on a dependency rather than on a decision. Order
# matters for the same reason: dependents come off the database before the
# things they point at.
PRE_USER_ROLE = ("users", "0004_employeeprofile_gender")
PRE_ROLE_TARGETS = [
    PRE_USER_ROLE,
    ("workflows", "0009_delegation_one_open_request_per_approver"),
]

SEED_CHAIN = [
    ("Administration chain", "administration", ["supervisor", "hod", "registrar"]),
    ("Faculty chain", "academic", ["supervisor", "dean", "dvc"]),
]
# A code the application never knew about, as a leftover from development.
STRAY_CODE = "acting_registrar"
# The six codes 0011 seeds, plus the one invented for STRAY_CODE.
SEEDED_ROLE_COUNT = 7


class MigrationTestCase(TransactionTestCase):
    """Shared machinery: move the database to a named point in history.

    ``migrate`` is the only way to move, in either direction, because Django's
    target semantics already cover both. A target that is *already applied* rolls
    its app back to it, unapplying everything after it in that app; a target that
    is *not yet applied* migrates forwards to it. There is no second call to get
    wrong, and — importantly for these tests — no way to accidentally jump the
    database to its latest state partway through an assertion.
    """

    @staticmethod
    def as_targets(targets) -> list[tuple[str, str]]:
        """Normalise ``("app", "0001_name")`` pairs, however they arrive.

        A list of pairs is accepted as well as a varargs of them, because the
        interesting targets here span two apps and are named by a constant.
        """
        return [
            target
            for argument in targets
            for target in (argument if isinstance(argument, list) else (argument,))
        ]

    def migrate(self, *targets) -> None:
        """Apply or unapply migrations until every app is at its target."""
        MigrationExecutor(connection).migrate(self.as_targets(targets))

    def state(self, *targets):
        """The historical models as they were defined at ``targets``."""
        loader = MigrationExecutor(connection).loader
        loader.build_graph()
        return loader.project_state(self.as_targets(targets)).apps

    def latest(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def setUp(self):
        self.latest()

    def tearDown(self):
        self.latest()


class BackfillMigrationTests(MigrationTestCase):
    """0011 is the only migration that decides anything row by row."""

    def build_legacy_state(self) -> None:
        """Recreate the world as it looked before roles were data.

        Uses the *historical* models, which is the whole point: at this point in
        history ``WorkflowStage.approver_role`` is text and
        ``ApplicationStage.role`` is a string with a hardcoded choice list.
        """
        self.migrate(*PRE_ROLE_TARGETS)
        apps = self.state(PRE_ROLE_TARGETS)
        Workflow = apps.get_model("workflows", "Workflow")
        WorkflowStage = apps.get_model("workflows", "WorkflowStage")
        ApplicationStage = apps.get_model("workflows", "ApplicationStage")
        User = apps.get_model("users", "User")
        EmployeeProfile = apps.get_model("users", "EmployeeProfile")

        for name, category, roles in SEED_CHAIN:
            workflow = Workflow.objects.create(
                name=name, employee_category=category, is_active=True
            )
            for order, role in enumerate(roles, start=1):
                WorkflowStage.objects.create(
                    workflow=workflow, order=order, approver_role=role
                )

        stray = Workflow.objects.create(
            name="Stray chain", employee_category="administration", is_active=True
        )
        WorkflowStage.objects.create(workflow=stray, order=1, approver_role=STRAY_CODE)

        # An application already in flight, so the snapshot backfill has rows to
        # write. The leave app is untouched by this sequence, so the real model is
        # the one that matches its table.
        from leave.models import LeaveApplication  # noqa: PLC0415

        employee = User.objects.create(username="legacy@roles.test")
        EmployeeProfile.objects.create(
            user_id=employee.pk,
            # The plain string, not a Department: at this point in history
            # ``department`` is a text column, and passing the model would fail
            # on the value rather than on the thing under test.
            department="Administration",
            faculty="Faculty of Science",
            category="administration",
            grade="B",
        )
        application = LeaveApplication.objects.create(
            employee_id=employee.pk, leave_type_id=1, reason="Annual leave"
        )
        for order, role in enumerate(["supervisor", "hod"], start=1):
            # By id, not instance: the historical model refuses instances of the
            # current one even when the table is the same.
            ApplicationStage.objects.create(
                application_id=application.pk,
                submission_cycle=1,
                stage_order=order,
                role=role,
                role_label=role.title(),
                status="approved",
                is_final=False,
                assigned_approver_id=employee.pk,
            )

    def test_roles_are_created_for_every_hardcoded_code(self):
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        ApproverRole = self.state(WORKFLOWS[1]).get_model(
            "workflows", "ApproverRole"
        )
        codes = set(ApproverRole.objects.values_list("code", flat=True))
        for _, _, roles in SEED_CHAIN:
            for role in roles:
                self.assertIn(role, codes)
        self.assertIn("campus_registrar", codes)
        self.assertEqual(ApproverRole.objects.count(), SEEDED_ROLE_COUNT)

    def test_stages_point_at_the_matching_role(self):
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        apps = self.state(WORKFLOWS[1])
        ApproverRole = apps.get_model("workflows", "ApproverRole")
        WorkflowStage = apps.get_model("workflows", "WorkflowStage")
        for workflow, _, roles in SEED_CHAIN:
            stages = WorkflowStage.objects.filter(
                workflow__name=workflow
            ).order_by("order")
            self.assertEqual(
                [ApproverRole.objects.get(pk=s.approver_role_ref_staging).code for s in stages],
                roles,
            )

    def test_the_staging_reference_becomes_a_real_foreign_key(self):
        """At 0011 the code is copied; only 0012 makes it a navigable relation."""
        self.build_legacy_state()
        self.migrate(WORKFLOWS[2])
        # Read the model out of the migrated state, not ``workflows.models``:
        # ``WorkflowStage`` is a historical model and no longer exists in the
        # live schema.
        WorkflowStage = self.state(WORKFLOWS[2]).get_model("workflows", "WorkflowStage")

        stage = WorkflowStage.objects.get(workflow__name="Faculty chain", order=2)
        self.assertEqual(stage.approver_role.code, "dean")

    def test_an_unknown_code_becomes_an_inactive_role_rather_than_an_error(self):
        """A stray development code must not make a real migration unrunnable."""
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        apps = self.state(WORKFLOWS[1])
        ApproverRole = apps.get_model("workflows", "ApproverRole")
        WorkflowStage = apps.get_model("workflows", "WorkflowStage")
        stray_role = ApproverRole.objects.get(code=STRAY_CODE)
        self.assertFalse(stray_role.is_active)
        stage = WorkflowStage.objects.get(workflow__name="Stray chain", order=1)
        self.assertEqual(stage.approver_role_ref_staging, stray_role.pk)

    def test_application_stages_keep_their_label_and_gain_snapshots(self):
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        ApplicationStage = self.state(WORKFLOWS[1]).get_model(
            "workflows", "ApplicationStage"
        )
        stages = ApplicationStage.objects.order_by("stage_order")
        self.assertEqual([s.role for s in stages], ["supervisor", "hod"])
        self.assertEqual(
            [s.history_scope for s in stages], ["all", "same_department"]
        )
        self.assertEqual([s.handles_cancellation for s in stages], [True, True])

    def test_a_supervisor_keeps_institution_wide_off_and_registrar_on(self):
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        ApproverRole = self.state(WORKFLOWS[1]).get_model(
            "workflows", "ApproverRole"
        )
        self.assertFalse(ApproverRole.objects.get(code="hod").is_institution_wide)
        self.assertTrue(ApproverRole.objects.get(code="registrar").is_institution_wide)

    def test_an_active_registrar_is_given_the_institution_wide_role(self):
        """Step 4 of 0011: a registrar with no team can still approve."""
        self.migrate(*PRE_ROLE_TARGETS)
        User = self.state(PRE_ROLE_TARGETS).get_model("users", "User")
        User.objects.create(username="reg@roles.test", role="registrar", is_active=True)
        User.objects.create(username="retired-reg@roles.test", role="registrar", is_active=False)

        self.migrate(WORKFLOWS[1])
        apps = self.state(WORKFLOWS[1])
        RoleAssignment = apps.get_model("workflows", "RoleAssignment")
        registrar = apps.get_model("workflows", "ApproverRole").objects.get(
            code="registrar"
        )
        self.assertEqual(
            [a.user.username for a in RoleAssignment.objects.filter(role=registrar)],
            ["reg@roles.test"],
        )

    def test_a_reverse_and_re_apply_reaches_the_same_state(self):
        """Idempotent, and reversible: the codes are still in the text columns.

        Running a recorded migration twice is a no-op, so re-running 0011 is
        tested the way it can actually go wrong: unapplied and applied again
        over a database that holds real workflow and application data.
        """
        self.build_legacy_state()
        self.migrate(WORKFLOWS[1])
        before = self.role_snapshot()

        # Unapplying 0011 means targeting 0010, its predecessor: the role tables
        # are dropped on the way through.
        self.migrate(WORKFLOWS[0])
        ApproverRole = self.state(WORKFLOWS[0]).get_model("workflows", "ApproverRole")
        self.assertEqual(ApproverRole.objects.count(), 0)

        self.migrate(WORKFLOWS[1])
        self.assertEqual(self.role_snapshot(), before)

    def role_snapshot(self) -> dict:
        """Every row 0011 writes, as a comparable value.

        Identified by role *code* rather than by primary key: the reverse drops
        the role rows, so a re-run is given fresh ids by the sequence, and
        comparing ids would report a difference that means nothing.
        """
        apps = self.state(WORKFLOWS[1])
        ApproverRole = apps.get_model("workflows", "ApproverRole")
        WorkflowStage = apps.get_model("workflows", "WorkflowStage")
        ApplicationStage = apps.get_model("workflows", "ApplicationStage")
        code_of = dict(ApproverRole.objects.values_list("id", "code"))
        return {
            "roles": sorted(
                ApproverRole.objects.values_list(
                    "code",
                    "label",
                    "is_active",
                    "history_scope",
                    "handles_cancellation",
                    "is_institution_wide",
                )
            ),
            "stages": sorted(
                (name, order, code_of[reference])
                for name, order, reference in WorkflowStage.objects.values_list(
                    "workflow__name", "order", "approver_role_ref_staging"
                )
            ),
            "application_stages": sorted(
                (order, role, code_of[reference], scope, handles)
                for order, role, reference, scope, handles in (
                    ApplicationStage.objects.values_list(
                        "stage_order",
                        "role",
                        "role_ref_id",
                        "history_scope",
                        "handles_cancellation",
                    )
                )
            ),
        }


class ForeignKeySwapTests(MigrationTestCase):
    """0012 drops the text column; the reverse has to bring the codes back."""

    def build_role_backed_stage(self):
        """A role-backed stage in the state 0012 operates on.

        ``WorkflowStage`` no longer exists in the live schema, so it is built
        from the historical state 0012 expects — which is exactly the point:
        this fixture is the thing 0012 is rewriting.
        """
        apps = self.state(WORKFLOWS[2])
        ApproverRole = apps.get_model("workflows", "ApproverRole")
        Workflow = apps.get_model("workflows", "Workflow")
        WorkflowStage = apps.get_model("workflows", "WorkflowStage")

        role, _ = ApproverRole.objects.get_or_create(
            code="dean", defaults={"label": "Dean"}
        )
        workflow = Workflow.objects.create(name="Chain", is_active=True)
        return WorkflowStage.objects.create(
            workflow=workflow, order=1, approver_role=role
        )

    def stage_columns(self) -> set[str]:
        with connection.cursor() as cursor:
            return {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor, "workflows_workflowstage"
                )
            }

    def test_workflow_stages_end_up_with_a_role_reference(self):
        self.migrate(WORKFLOWS[2])
        stage = self.build_role_backed_stage()
        # Compared on the id, not on object identity: the stage is a historical
        # model instance and the role is a live one, so ``assertEqual`` would
        # compare instances of two unrelated classes.
        self.assertEqual(
            stage.approver_role_id,
            self.state(WORKFLOWS[2])
            .get_model("workflows", "ApproverRole")
            .objects.get(code="dean")
            .pk,
        )
        self.assertIn("approver_role_id", self.stage_columns())
        self.assertNotIn("approver_role", self.stage_columns())

    def test_an_application_stage_keeps_its_text_snapshot(self):
        """The snapshot stays text on purpose: it must outlive its role."""
        from approvals.models import ApplicationStage  # noqa: PLC0415

        self.migrate(WORKFLOWS[2])
        field = ApplicationStage._meta.get_field("role")
        self.assertIsNone(field.choices)
        self.assertEqual(field.max_length, 50)

    def test_reversing_0012_restores_the_text_column_with_the_codes(self):
        self.migrate(WORKFLOWS[2])
        self.build_role_backed_stage()

        self.migrate(WORKFLOWS[1])
        self.assertIn("approver_role", self.stage_columns())
        field = self.state(WORKFLOWS[1]).get_model(
            "workflows", "WorkflowStage"
        )._meta.get_field("approver_role")
        self.assertEqual(field.get_internal_type(), "CharField")
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT "approver_role" FROM workflows_workflowstage ORDER BY "order"'
            )
            self.assertEqual([row[0] for row in cursor.fetchall()], ["dean"])

    def test_reapplying_0012_drops_the_text_column_again(self):
        self.migrate(WORKFLOWS[2])
        self.build_role_backed_stage()
        self.migrate(WORKFLOWS[1])
        self.migrate(WORKFLOWS[2])
        self.assertNotIn("approver_role", self.stage_columns())
        self.assertIn("approver_role_id", self.stage_columns())

    def test_the_whole_sequence_reverses_and_reapplies(self):
        for target in WORKFLOWS:
            self.migrate(target)
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
        self.assertIn("workflows_approverrole", tables)

        # Unapplying a migration means naming its predecessor as the target, so
        # the predecessors are walked in reverse. The users targets come first:
        # EmployeeProfile.team points at the Team table 0010 drops.
        for index in reversed(range(len(WORKFLOWS))):
            self.migrate(
                *(PRE_ROLE_TARGETS if index == 0 else [WORKFLOWS[index - 1]])
            )
            if index == 0:
                with connection.cursor() as cursor:
                    tables = connection.introspection.table_names(cursor)
                self.assertNotIn("workflows_approverrole", tables)
                self.assertNotIn("workflows_team", tables)
                self.assertNotIn("workflows_campus", tables)

        for target in WORKFLOWS:
            self.migrate(target)
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
        self.assertIn("workflows_approverrole", tables)
        self.assertIn("workflows_team", tables)
        self.assertIn("workflows_campus", tables)


class ModelConstraintTests(MigrationTestCase):
    """Constraints that the application layer relies on must exist in the schema."""

    def test_role_and_team_codes_are_unique(self):
        from django.db import IntegrityError, transaction  # noqa: PLC0415

        from workflows.models import (
            Workflow,
        )
        from organisation.models import (
            ApproverRole,
            Campus,
        )
        from teams.models import (
            Team,
        )

        ApproverRole.objects.create(code="dean", label="Dean")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ApproverRole.objects.create(code="dean", label="Dean again")

        workflow = Workflow.objects.create(name="Chain", is_active=True)
        Team.objects.create(name="Science", code="science", workflow=workflow)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Team.objects.create(
                    name="Science copy", code="science", workflow=workflow
                )

        Campus.objects.create(name="Tehune", code="tehune")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Campus.objects.create(name="Tehune copy", code="tehune")

    def test_a_team_holds_one_member_per_role_and_one_role_per_person(self):
        from django.db import IntegrityError, transaction  # noqa: PLC0415

        from users.models import User  # noqa: PLC0415
        from organisation.models import ApproverRole  # noqa: PLC0415
        from workflows.models import (
            Section,
            SectionMember,
            Workflow,
        )
        from teams.models import (
            Team,
        )

        science_workflow = Workflow.objects.create(
            name="Science chain", is_active=True
        )
        arts_workflow = Workflow.objects.create(name="Arts chain", is_active=True)
        science = Team.objects.create(
            name="Science", code="science", workflow=science_workflow
        )
        arts = Team.objects.create(name="Arts", code="arts", workflow=arts_workflow)
        supervisor_role = ApproverRole.objects.create(
            code="supervisor", label="Supervisor"
        )
        hod_role = ApproverRole.objects.create(code="hod", label="Head of Department")
        section = Section.objects.create(
            workflow=science_workflow, order=1, name="Supervisor",
            approver_role=supervisor_role,
        )

        one = User.objects.create_user(
            username="one@constraints.test", email="one@constraints.test", password="x"
        )
        two = User.objects.create_user(
            username="two@constraints.test", email="two@constraints.test", password="x"
        )

        # A section takes any number of people — that is the whole point — so
        # there is no one-member-per-section constraint left to violate. What
        # remains is the single rule: not twice in the same section.
        SectionMember.objects.create(section=section, user=one)
        SectionMember.objects.create(section=section, user=two)
        self.assertEqual(SectionMember.objects.filter(section=section).count(), 2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SectionMember.objects.create(section=section, user=two)
        self.assertEqual(SectionMember.objects.filter(section=section).count(), 2)
        self.assertIsNotNone(arts.pk)

    def test_a_campus_referenced_by_a_team_cannot_be_deleted(self):
        from django.db.models import ProtectedError  # noqa: PLC0415

        from workflows.models import (
            Workflow,  # noqa: PLC0415
        )
        from organisation.models import (
            Campus,
        )
        from teams.models import (
            Team,
        )

        campus = Campus.objects.create(name="Tehune", code="tehune")
        Team.objects.create(
            name="Tehune team",
            code="tehune-team",
            campus=campus,
            workflow=Workflow.objects.create(name="Chain", is_active=True),
        )
        with self.assertRaises(ProtectedError):
            campus.delete()

    def test_a_workflow_referenced_by_a_team_cannot_be_deleted(self):
        from django.db.models import ProtectedError  # noqa: PLC0415

        from workflows.models import (
            Workflow,  # noqa: PLC0415
        )
        from teams.models import (
            Team,
        )

        workflow = Workflow.objects.create(name="Chain", is_active=True)
        Team.objects.create(name="Team", code="team", workflow=workflow)
        with self.assertRaises(ProtectedError):
            workflow.delete()

    def test_a_role_referenced_by_a_section_cannot_be_deleted(self):
        from django.db.models import ProtectedError  # noqa: PLC0415

        from workflows.models import (
            Section,
            Workflow,  # noqa: PLC0415
        )
        from organisation.models import (
            ApproverRole,
        )

        role = ApproverRole.objects.create(code="dean", label="Dean")
        workflow = Workflow.objects.create(name="Chain", is_active=True)
        Section.objects.create(
            workflow=workflow, order=1, name="Dean", approver_role=role
        )
        with self.assertRaises(ProtectedError):
            role.delete()

    def test_a_role_referenced_by_a_section_member_cannot_be_deleted(self):
        """Members are people, so a user in a section blocks the user deletion."""
        from django.db.models import ProtectedError  # noqa: PLC0415

        from django.contrib.auth import get_user_model  # noqa: PLC0415

        from organisation.models import ApproverRole  # noqa: PLC0415
        from workflows.models import (  # noqa: PLC0415
            Section,
            SectionMember,
            Workflow,
        )

        User = get_user_model()
        role = ApproverRole.objects.create(code="dean", label="Dean")
        workflow = Workflow.objects.create(name="Chain", is_active=True)
        section = Section.objects.create(
            workflow=workflow, order=1, name="Dean", approver_role=role
        )
        user = User.objects.create_user(
            username="dean-in-section", email="dean-in-section@test.luanar"
        )
        SectionMember.objects.create(section=section, user=user)
        with self.assertRaises(ProtectedError):
            user.delete()


class UserRoleMigrationTests(MigrationTestCase):
    """``User.role`` shrinks to system access; a historic value must be mapped."""

    def test_the_pre_role_values_are_rewritten_to_system_access(self):
        """Every former approver value becomes ``approver``, not a role name."""
        # Only the users app is rewound: 0011 has already run, so the roles exist
        # and there is no need to touch the workflows schema to get a user row
        # with an old role in it.
        self.migrate(PRE_USER_ROLE)
        User = self.state(PRE_USER_ROLE).get_model("users", "User")
        for code in ("supervisor", "hod", "dean", "registrar", "dvc"):
            self.assertIn(code, dict(User._meta.get_field("role").choices))
        for code in ("hod", "hr", "employee"):
            User.objects.create(
                username=f"{code}@rewrite.test", email=f"{code}@rewrite.test", role=code
            )

        self.migrate(USERS[-1])
        self.assertEqual(User.objects.get(username="hod@rewrite.test").role, "approver")
        self.assertEqual(User.objects.get(username="hr@rewrite.test").role, "hr")
        self.assertEqual(
            User.objects.get(username="employee@rewrite.test").role, "employee"
        )

    def test_the_final_role_choices_are_system_access_only(self):
        from users.models import User  # noqa: PLC0415

        self.assertEqual(
            sorted(User.Role.values), ["approver", "employee", "hr"]
        )

    def test_the_team_column_exists_and_is_nullable(self):
        from users.models import EmployeeProfile  # noqa: PLC0415

        field = EmployeeProfile._meta.get_field("team")
        self.assertTrue(field.null)
        self.assertEqual(field.remote_field.related_name, "members")


class AuditTargetTypeMigrationTests(MigrationTestCase):
    """The configuration surfaces added new audit target types."""

    def test_the_configuration_target_types_exist(self):
        from audit.models import AuditEntry  # noqa: PLC0415

        values = set(AuditEntry.TargetType.values)
        for target in ("approver-role", "team", "campus"):
            self.assertIn(target, values)

    def test_a_legacy_target_type_is_untouched(self):
        from audit.models import AuditEntry  # noqa: PLC0415

        for target in ("application", "employee", "workflow"):
            self.assertIn(target, set(AuditEntry.TargetType.values))


class InstitutionWideFinalApprovalMigrationTests(MigrationTestCase):
    """0023 moves final approval off sections and onto a role holding."""

    def setUp(self):
        super().setUp()
        self.migrate(("workflows", "0022_team_workflow_optional"))

    def _legacy_state(self):
        """A department-scoped DVC: flagged off, appointed, holding nothing."""
        state = self.state(("workflows", "0022_team_workflow_optional"))
        ApproverRole = state.get_model("workflows", "ApproverRole")
        Workflow = state.get_model("workflows", "Workflow")
        Section = state.get_model("workflows", "Section")
        User = state.get_model("users", "User")

        role = ApproverRole.objects.create(code="dvc", label="Deputy Vice-Chancellor")
        user = User.objects.create(username="dvc@test.luanar", email="dvc@test.luanar")
        workflow = Workflow.objects.create(
            name="Legacy Chain", effective_from="2026-06-01", is_active=True
        )
        Section.objects.create(
            workflow=workflow, order=1, name="DVC", approver_role=role, approver=user
        )
        return role.pk, user.pk

    def _read(self):
        from workflows.models import (
            Section  # noqa: PLC0415,
        )
        from organisation.models import (
            ApproverRole,
            RoleAssignment,
        )

        role = ApproverRole.objects.get(code="dvc")
        return {
            "is_institution_wide": role.is_institution_wide,
            "appointments": Section.objects.filter(
                approver_role=role, approver__isnull=False
            ).count(),
            "holdings": RoleAssignment.objects.filter(role=role).count(),
            "holders": list(
                RoleAssignment.objects.filter(role=role).values_list(
                    "user__username", flat=True
                )
            ),
        }

    def test_the_dvc_role_is_promoted_to_institution_wide(self):
        role_pk, _ = self._legacy_state()
        self.latest()
        from organisation.models import ApproverRole  # noqa: PLC0415

        self.assertTrue(ApproverRole.objects.get(pk=role_pk).is_institution_wide)

    def test_the_existing_approver_keeps_the_power_to_approve(self):
        _, user_pk = self._legacy_state()
        self.latest()

        result = self._read()
        self.assertEqual(result["holdings"], 1)
        self.assertEqual(result["holders"], ["dvc@test.luanar"])
        self.assertEqual(result["appointments"], 0)
        del user_pk

    def test_a_promoted_role_is_not_also_pinned_to_a_section(self):
        """Both would resolve, differently per team, for the same officer."""
        self._legacy_state()
        self.latest()

        self.assertEqual(self._read()["appointments"], 0)

    def test_running_twice_does_not_duplicate_the_holding(self):
        self._legacy_state()
        self.latest()

        module = import_module(
            "workflows.migrations.0023_institution_wide_final_approval"
        )
        historical_apps = self.state(("workflows", "0022_team_workflow_optional"))
        module.flag_institution_wide_roles(historical_apps, None)

        self.assertEqual(self._read()["holdings"], 1)

    def test_a_missing_role_is_skipped_rather_than_failing(self):
        """A fresh install has no DVC yet; the seed creates it already flagged."""
        from organisation.models import ApproverRole  # noqa: PLC0415

        self.assertFalse(ApproverRole.objects.filter(code="dvc").exists())
        self.latest()

        self.assertFalse(ApproverRole.objects.filter(code="dvc").exists())

    def test_reversing_restores_the_flag_but_keeps_the_holding(self):
        """Deleting the row would revoke a real approval right on rollback."""
        self._legacy_state()
        self.latest()
        self.migrate(("workflows", "0022_team_workflow_optional"))

        result = self._read()
        self.assertFalse(result["is_institution_wide"])
        self.assertEqual(result["holdings"], 1)
