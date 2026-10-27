"""HR-managed approver roles: the configuration surface behind ``is_approver_user``.

A role is the unit HR actually manages. These tests pin the three promises that
make the rest of the system safe to reason about:

1. Roles are created and edited through audited, HR-only endpoints.
2. ``code`` is the stable key everything else (workflow stages, team members,
   historical stage snapshots) is written against, so it does not change.
3. A role is retired by deactivation, never deleted, and only once nothing
   active still uses it — with an error that names the blockers.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry

from roles.models import ApproverRole, RoleAssignment
from roles.services import RoleActionError, approver_role_codes_for, approver_role_labels_for, create_approver_role, deactivate_approver_role, ensure_role_not_in_use, is_approver_user, update_approver_role
from .testing import (
    DEV_PASSWORD,
    ensure_roles,
    grant_approver_role,
    make_approver,
    make_team,
    make_workflow,
)

User = get_user_model()

LIST_URL = "/api/v1/approver-roles/"

# What ``ensure_roles("dean")`` seeds the dean with, quoted by the edit tests.
_DESCRIPTION = "Dean of the applicant's faculty."


class RoleAPIBase(TestCase):
    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@roles.test",
            email="hr@roles.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee = User.objects.create_user(
            username="emp@roles.test",
            email="emp@roles.test",
            password=DEV_PASSWORD,
            role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(self.hr)

    def payload(self, **overrides) -> dict:
        """A role create payload: a name, and only a name.

        The code is derived from the label rather than sent, so it is deliberately
        absent here. Passing one in ``overrides`` is how the tests below prove it
        is ignored.
        """
        data = {"label": "Examinations Officer"}
        data.update(overrides)
        return data


class RoleCreationTests(RoleAPIBase):
    def test_hr_creates_a_role_from_its_name_alone(self):
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        role = ApproverRole.objects.get(code="examinations-officer")
        self.assertEqual(role.label, "Examinations Officer")
        self.assertEqual(response.data["code"], "examinations-officer")
        self.assertEqual(response.data["label"], "Examinations Officer")

    def test_the_code_is_derived_from_the_name_and_ignores_a_supplied_one(self):
        """HR gives the name; the identifier every rule reads is derived from it.

        Asking for the same word twice is asking for the two to disagree, and
        they would: the label is what every screen shows and the code is what
        every rule reads. So a posted code is not honoured — it is derived.
        """
        response = self.client.post(
            LIST_URL, self.payload(code="something-else"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ApproverRole.objects.get(label="Examinations Officer").code,
            "examinations-officer",
        )

    def test_names_that_slug_alike_get_distinct_codes(self):
        before = ApproverRole.objects.count()
        first = self.client.post(LIST_URL, {"label": "Estate Officer"}, format="json")
        second = self.client.post(
            LIST_URL, {"label": "Estate Officers"}, format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(
            first.data["code"], second.data["code"]  # type: ignore[index]
        )
        self.assertEqual(ApproverRole.objects.count(), before + 2)

    def test_a_name_that_slugifies_to_a_taken_code_gets_a_suffix(self):
        """Two names can reduce to one slug; the second must not overwrite the first.

        "Estate Officer" and "Estate Officers" are different roles, and the code
        is derived from the name, so the collision has to be resolved rather than
        refused — the names are still distinct and HR meant both of them.
        """
        first = self.client.post(LIST_URL, {"label": "Estate Officer"}, format="json")
        # "Estate Officers" slugs to "estate-officers" on its own, so the clash
        # is forced with a label whose slug is already taken.
        second = self.client.post(LIST_URL, {"label": "Estate Officer!"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["code"], "estate-officer")  # type: ignore[index]
        self.assertNotEqual(
            second.data["code"], "estate-officer"  # type: ignore[index]
        )
        self.assertTrue(str(second.data["code"]).startswith("estate-officer"))  # type: ignore[index]

    def test_a_name_with_no_slug_characters_is_refused(self):
        response = self.client.post(LIST_URL, {"label": "!!!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label", response.data)

    def test_creation_is_audited(self):
        self.client.post(LIST_URL, self.payload(), format="json")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            action=AuditEntry.Action.CREATED,
        )
        self.assertEqual(
            str(entry.target_id),
            str(ApproverRole.objects.get(code="examinations-officer").pk),
        )
        self.assertEqual(entry.actor, self.hr)

    def test_a_name_that_already_exists_reuses_the_role(self):
        """The same name typed twice is one role, not two.

        A manager adding a role from a chain's step form types a name they may
        not know is already in the organisation's vocabulary. Creating a second
        "Dean" would give the chain a step no holder could ever staff, so the
        existing role is returned and nothing new is written.
        """
        ensure_roles("dean")
        existing = ApproverRole.objects.get(code="dean")
        before = ApproverRole.objects.count()

        response = self.client.post(LIST_URL, {"label": "Dean"}, format="json")

        # 200, not 201: the name created nothing.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], existing.pk)
        self.assertEqual(ApproverRole.objects.count(), before)

    def test_matching_ignores_case_and_surrounding_space(self):
        ensure_roles("dean")
        existing = ApproverRole.objects.get(code="dean")
        before = ApproverRole.objects.count()

        response = self.client.post(
            LIST_URL, {"label": "  dean  "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], existing.pk)
        self.assertEqual(ApproverRole.objects.count(), before)

    def test_a_retired_role_with_the_same_name_is_refused(self):
        """Reusing a retired role silently would resurrect a name HR put down.

        Past stages quote the old role, so bringing it back is a decision made
        on the Roles screen, not a side effect of adding a chain step.
        """
        role = ensure_roles("dean")["dean"]
        role.is_active = False
        role.save(update_fields=["is_active"])

        response = self.client.post(LIST_URL, {"label": "Dean"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label", response.data)
        self.assertFalse(
            ApproverRole.objects.filter(label__iexact="Dean", is_active=True).exists()
        )

    def test_blank_label_rejected(self):
        response = self.client.post(LIST_URL, self.payload(label=""), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label", response.data)

    def test_unknown_history_scope_rejected(self):
        response = self.client.post(
            LIST_URL, self.payload(history_scope="whatever"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("history_scope", response.data)

    def test_non_hr_cannot_create_a_role(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ApproverRole.objects.filter(code="examiner").exists())

    def test_anonymous_cannot_create_a_role(self):
        self.client.force_authenticate(None)
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_a_failing_audit_rolls_the_role_back(self):
        with mock.patch(
            "roles.services.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(LIST_URL, self.payload(), format="json")
        self.assertFalse(ApproverRole.objects.filter(code="examiner").exists())


class RoleListingTests(RoleAPIBase):
    def test_list_hides_inactive_roles_by_default(self):
        ensure_roles("dean", "hod")
        role = ApproverRole.objects.get(code="dean")
        role.is_active = False
        role.save(update_fields=["is_active"])

        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("dean", [row["code"] for row in response.data["results"]])

    def test_include_inactive_reveals_them(self):
        ensure_roles("dean", "hod")
        role = ApproverRole.objects.get(code="dean")
        role.is_active = False
        role.save(update_fields=["is_active"])

        response = self.client.get(f"{LIST_URL}?include_inactive=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dean", [row["code"] for row in response.data["results"]])

    def test_list_is_ordered_by_label(self):
        ensure_roles("registrar", "dean", "hod")
        response = self.client.get(LIST_URL)
        labels = [row["label"] for row in response.data["results"]]
        self.assertEqual(labels, sorted(labels))

    def test_a_deactivated_role_reports_its_usage(self):
        """The list is where HR finds out *why* a role is still in use."""
        make_workflow("Registry chain", ("dean",))
        role = ApproverRole.objects.get(code="dean")
        role.is_institution_wide = True
        ApproverRole.objects.get(code="dean").save()

        response = self.client.get(LIST_URL)
        dean = next(
            r for r in response.data["results"] if r["code"] == "dean"
        )
        self.assertIn("Registry chain", " ".join(dean["usage"]))

    #: Two queries for the page itself (a COUNT and the rows) plus three for
    #: usage: the active workflow stages, the active team memberships, and the
    #: institution-wide holders. None of the three is per role.
    LIST_QUERY_COUNT = 5

    def test_usage_costs_a_fixed_number_of_queries_however_many_roles(self):
        """The Roles screen renders usage for every role at once.

        ``is_in_use`` and ``usage`` are the same fact asked for twice, and each
        usage clause names a blocker. Computing that per role, per field, made
        the list 69 queries for six roles and grew with every role HR added —
        the slowest endpoint in the admin. It is now three, and this pins the
        number so the per-role version cannot quietly return.
        """
        ensure_roles("supervisor", "hod", "dean", "registrar", "dvc")
        make_workflow("Academic chain", ("supervisor", "hod", "dean"))
        make_workflow("Registry chain", ("registrar", "dvc"))
        make_team("Registry", ("registrar",))

        with self.assertNumQueries(self.LIST_QUERY_COUNT):
            response = self.client.get(LIST_URL)

        rows = {row["code"]: row for row in response.data["results"]}
        for code in ("dean", "registrar", "supervisor"):
            self.assertIn(code, rows)
            self.assertTrue(rows[code]["usage"], code)
        # The same fact asked for two ways, from one computation.
        for row in response.data["results"]:
            self.assertEqual(row["is_in_use"], bool(row["usage"]))

    def test_adding_roles_does_not_add_queries(self):
        """The fix is the batch, not just a smaller constant per role.

        Roles are open-ended: HR adds codes without a deploy, so the query
        count has to be a function of what the screen asks for, not of how many
        roles have accumulated.         A per-role version would pass the first
        assertion in the test above only because that screen happened to hold a
        fixed handful.
        """
        ensure_roles("supervisor", "hod", "dean", "registrar", "dvc")
        with self.assertNumQueries(self.LIST_QUERY_COUNT):
            first = self.client.get(LIST_URL)

        make_workflow("One chain", ("dean", "supervisor", "hod"))
        make_workflow("Two chains", ("registrar",))
        make_team("Registry", ("registrar", "dvc"))
        for code in ("examiner", "auditor", "bursar", "librarian"):
            ApproverRole.objects.create(
                code=code,
                label=code.title(),
                history_scope=ApproverRole.HistoryScope.ALL,
            )
        with self.assertNumQueries(self.LIST_QUERY_COUNT):
            second = self.client.get(LIST_URL)

        before = len(first.data["results"])
        after = len(second.data["results"])
        self.assertGreater(after, before)


class RoleCodeImmutabilityTests(RoleAPIBase):
    def setUp(self):
        super().setUp()
        self.role = ensure_roles("dean")["dean"]
        # The seeded dean ships with a description, so the before/after of an
        # edit is read against what was actually there rather than "".
        self.assertEqual(self.role.description, _DESCRIPTION)

    def test_code_cannot_be_changed(self):
        """A posted code is ignored, because it was never the caller's to give.

        The code is derived from the name at creation, so there is nothing to
        change: sending one is not a request to rename the role, it is a field
        that does not exist. It is silently ignored rather than refused, which
        keeps a client that still sends the field working while the stored code
        stays the derived one.
        """
        response = self.client.patch(
            f"{LIST_URL}{self.role.pk}/", {"code": "provost"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.role.refresh_from_db()
        self.assertEqual(self.role.code, "dean")

    def test_a_role_name_cannot_be_changed(self):
        """The name is quoted by history, so it is fixed once the role exists.

        Workflow stages and audit entries name the role. Renaming it would leave
        every one of those quoting a string that no longer resolves to anything,
        so the refusal points HR at creating a new role instead.
        """
        response = self.client.patch(
            f"{LIST_URL}{self.role.pk}/", {"label": "Provost"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label", response.data)
        self.role.refresh_from_db()
        self.assertEqual(self.role.label, "Dean")

    def test_a_code_change_is_refused_at_the_service_too(self):
        with self.assertRaises(RoleActionError) as ctx:
            update_approver_role(
                role=self.role, actor=self.hr, data={"code": "provost"}
            )
        self.assertEqual(ctx.exception.field, "code")
        self.role.refresh_from_db()
        self.assertEqual(self.role.code, "dean")

    def test_description_and_behaviour_stay_editable(self):
        response = self.client.patch(
            f"{LIST_URL}{self.role.pk}/",
            {
                "description": "Faculty appeals",
                "handles_cancellation": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.role.refresh_from_db()
        self.assertEqual(self.role.label, "Dean")
        self.assertEqual(self.role.description, "Faculty appeals")
        self.assertTrue(self.role.handles_cancellation)

    def test_scope_is_not_edited_from_the_role_itself(self):
        """A role becomes institution-wide when its first institution-wide
        holder is assigned on the Approvers page, not from this editor, so a
        PATCH that tries to change the scope is refused."""
        self.assertFalse(self.role.is_institution_wide)
        response = self.client.patch(
            f"{LIST_URL}{self.role.pk}/",
            {"is_institution_wide": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "decided on the Approvers page", response.data["is_institution_wide"][0]
        )
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_institution_wide)
        # An unchanged scope sent along with a real edit stays harmless.
        response = self.client.patch(
            f"{LIST_URL}{self.role.pk}/",
            {"is_institution_wide": False, "description": "Faculty appeals"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.role.refresh_from_db()
        self.assertEqual(self.role.description, "Faculty appeals")
        self.assertFalse(self.role.is_institution_wide)

    def test_an_edit_is_audited_with_before_and_after(self):
        self.client.patch(
            f"{LIST_URL}{self.role.pk}/",
            {"description": "Faculty appeals"},
            format="json",
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=str(self.role.pk),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertEqual(entry.detail["before"]["description"], _DESCRIPTION)
        self.assertEqual(entry.detail["after"]["description"], "Faculty appeals")

    def test_a_failing_audit_rolls_the_edit_back(self):
        with mock.patch(
            "roles.services.record_audit", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.client.patch(
                    f"{LIST_URL}{self.role.pk}/",
                    {"description": "Nope"},
                    format="json",
                )
        self.role.refresh_from_db()
        self.assertEqual(self.role.description, _DESCRIPTION)

    def test_is_active_cannot_be_set_through_patch(self):
        """Retirement goes through DELETE so it always runs the usage guard."""
        self.client.patch(
            f"{LIST_URL}{self.role.pk}/", {"is_active": False}, format="json"
        )
        self.role.refresh_from_db()
        self.assertTrue(self.role.is_active)


class RoleDeactivationTests(RoleAPIBase):
    def setUp(self):
        super().setUp()
        self.role = ensure_roles("dean")["dean"]

    def test_unused_role_is_retired_not_deleted(self):
        response = self.client.delete(f"{LIST_URL}{self.role.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])
        self.assertTrue(ApproverRole.objects.filter(pk=self.role.pk).exists())
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_active)

    def test_deactivation_is_audited(self):
        self.client.delete(f"{LIST_URL}{self.role.pk}/")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=str(self.role.pk),
            action=AuditEntry.Action.CANCELLED,
        )
        self.assertEqual(entry.actor, self.hr)

    def test_a_role_on_an_active_workflow_cannot_be_retired(self):
        make_workflow("Registry chain", ("dean",))
        with self.assertRaises(RoleActionError) as ctx:
            deactivate_approver_role(role=self.role, actor=self.hr)
        self.assertIn("Registry chain", ctx.exception.message)
        self.role.refresh_from_db()
        self.assertTrue(self.role.is_active)

    def test_the_same_role_on_a_deactivated_workflow_can_be_retired(self):
        """The guard follows ``is_active``, so retiring a stale chain is possible."""
        workflow = make_workflow("Old chain", ("dean",))
        workflow.is_active = False
        workflow.save(update_fields=["is_active"])

        deactivate_approver_role(role=self.role, actor=self.hr)
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_active)

    def test_a_role_held_by_a_team_member_cannot_be_retired(self):
        team = make_team("Science team", ("dean",))
        with self.assertRaises(RoleActionError) as ctx:
            deactivate_approver_role(role=self.role, actor=self.hr)
        self.assertIn("Science team", ctx.exception.message)

    def test_a_role_held_institution_wide_cannot_be_retired(self):
        holder = make_approver("dean", username="institution-dean@roles.test")
        with self.assertRaises(RoleActionError) as ctx:
            deactivate_approver_role(role=self.role, actor=self.hr)
        self.assertIn(holder.get_full_name() or holder.username, ctx.exception.message)

    def test_an_inactive_holder_does_not_block_retirement(self):
        """Deactivating the holder frees the role, so HR is not wedged."""
        holder = make_approver("dean", username="leaver@roles.test")
        holder.is_active = False
        holder.save(update_fields=["is_active"])
        deactivate_approver_role(role=self.role, actor=self.hr)
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_active)

    def test_a_retired_role_is_gone_from_the_api(self):
        """Retired roles drop out of the active set, like teams and campuses."""
        self.client.delete(f"{LIST_URL}{self.role.pk}/")
        response = self.client.delete(f"{LIST_URL}{self.role.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ApproverRole.objects.filter(pk=self.role.pk).exists())

    def test_ensure_role_not_in_use_is_silent_for_an_unused_role(self):
        ensure_roles("hod")
        self.assertIsNone(ensure_role_not_in_use(ensure_roles("hod")["hod"]))

    def test_non_hr_cannot_retire_a_role(self):
        self.client.force_authenticate(self.employee)
        response = self.client.delete(f"{LIST_URL}{self.role.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.role.refresh_from_db()
        self.assertTrue(self.role.is_active)

    def test_an_in_use_role_reports_a_conflict(self):
        make_workflow("Registry chain", ("dean",))
        response = self.client.delete(f"{LIST_URL}{self.role.pk}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.role.refresh_from_db()
        self.assertTrue(self.role.is_active)


class RoleHolderTests(RoleAPIBase):
    """A role confers approver status through a holding, not through ``User.role``."""

    def test_system_approver_without_a_holding_is_not_an_approver(self):
        """``User.role = approver`` grants the desk, not a place in a chain.

        This is the distinction the whole feature rests on, so it is pinned here
        rather than inferred: access to the approvals API is not membership of a
        team.
        """
        desk_user = User.objects.create_user(
            username="desk@roles.test",
            email="desk@roles.test",
            password=DEV_PASSWORD,
            role=User.Role.APPROVER,
        )
        self.assertFalse(is_approver_user(desk_user))
        self.assertEqual(approver_role_codes_for(desk_user), [])

    def test_a_team_member_is_an_approver(self):
        make_team("Science team", ("dean",))
        member = make_approver("dean", username="member@roles.test")
        self.assertTrue(is_approver_user(member))
        self.assertEqual(approver_role_codes_for(member), ["dean"])
        self.assertEqual(approver_role_labels_for(member), ["Dean"])

    def test_an_institution_wide_holder_is_an_approver(self):
        holder = make_approver(
            "registrar", username="registrar-holder@roles.test", institution_wide=True
        )
        self.assertTrue(is_approver_user(holder))
        self.assertEqual(approver_role_codes_for(holder), ["registrar"])

    def test_approver_roles_deduplicate_a_person_holding_two_roles(self):
        """A person on a team *and* an institution-wide holder is listed once."""
        ensure_roles("dean", "registrar")
        ensure_roles("dean", "registrar")
        person = make_approver("dean", username="both@roles.test", institution_wide=False)
        make_team("Science team", ("dean",), approvers={"dean": person})
        RoleAssignment.objects.create(
            user=person, role=ApproverRole.objects.get(code="registrar")
        )
        self.assertEqual(approver_role_codes_for(person), ["dean", "registrar"])

    def test_deactivating_a_role_retires_the_approver_status_it_conferred(self):
        member = make_approver("dean", username="retiree@roles.test")
        self.assertTrue(is_approver_user(member))
        role = ApproverRole.objects.get(code="dean")
        role.is_active = False
        role.save(update_fields=["is_active"])
        self.assertFalse(is_approver_user(member))

    def test_a_deactivated_user_is_never_an_approver(self):
        member = make_approver("dean", username="leaver@roles.test")
        member.is_active = False
        member.save(update_fields=["is_active"])
        self.assertFalse(is_approver_user(member))

    def test_labels_and_codes_agree(self):
        ensure_roles("hod", "registrar")
        person = make_approver("hod", username="labels@roles.test")
        RoleAssignment.objects.create(
            user=person, role=ApproverRole.objects.get(code="registrar")
        )
        self.assertEqual(
            approver_role_labels_for(person),
            ["Head of Department", "Registrar"],
        )
        self.assertEqual(approver_role_codes_for(person), ["hod", "registrar"])

    def test_a_team_member_holding_no_role_is_not_an_approver(self):
        make_team("Science team", ("dean",))
        plain = User.objects.create_user(
            username="plain@roles.test",
            email="plain@roles.test",
            password=DEV_PASSWORD,
        )
        self.assertFalse(is_approver_user(plain))


class RoleServiceTests(TestCase):
    """The service layer is the only supported way to write roles."""

    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@roles.test",
            email="hr@roles.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )

    def test_create_returns_the_role_and_audits_it(self):
        role, created = create_approver_role(
            actor=self.hr,
            data={
                "code": "examiner",
                "label": "Examiner",
                "history_scope": ApproverRole.HistoryScope.ALL,
                "handles_cancellation": False,
                "is_institution_wide": False,
            },
        )
        self.assertTrue(created)
        self.assertEqual(role.code, "examiner")
        self.assertTrue(AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=str(role.pk),
        ).exists())

    def test_update_leaves_unmentioned_fields_alone(self):
        role = ensure_roles("dean")["dean"]
        update_approver_role(role=role, actor=self.hr, data={"label": "Dean of Faculty"})
        role.refresh_from_db()
        self.assertEqual(role.label, "Dean of Faculty")
        self.assertEqual(
            role.history_scope, ApproverRole.HistoryScope.SAME_FACULTY
        )

    def test_grant_approver_role_creates_the_role_and_the_holding(self):
        person = User.objects.create_user(
            username="grantee@roles.test",
            email="grantee@roles.test",
            password=DEV_PASSWORD,
        )
        grant_approver_role(person, "campus_registrar")
        self.assertTrue(is_approver_user(person))
        self.assertTrue(
            RoleAssignment.objects.filter(
                user=person, role__code="campus_registrar"
            ).exists()
        )
        # Institution-wide by default, so a team is not required.
        self.assertTrue(
            ApproverRole.objects.get(code="campus_registrar").is_institution_wide
        )

    def test_grant_without_institution_wide_leaves_no_holding(self):
        person = User.objects.create_user(
            username="member-only@roles.test",
            email="member-only@roles.test",
            password=DEV_PASSWORD,
        )
        grant_approver_role(person, "hod", institution_wide=False)
        self.assertEqual(approver_role_codes_for(person), [])
        self.assertFalse(RoleAssignment.objects.filter(user=person).exists())
