"""``sync_org_structure_from_provider`` mirrors the fixture directory.

Three themes: the first run creates every unit, a second run updates in
place (never duplicates), and role holders resolve to local users by email —
with vacancies and unresolvable employees clearing ``designated_approver``
rather than pointing at the wrong person.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from directory.factory import get_organization_provider
from org_structure.models import OrgUnit
from org_structure.services import sync_org_structure_from_provider

User = get_user_model()

#: Fixture-directory users (directory/fixtures/seed_data.json emails).
REGISTRAR_EMAIL = "registrar@test.luanar"
SUPERVISOR_EMAIL = "supervisor@test.luanar"
ADMIN_EMAIL = "admin@test.luanar"
VACANT_UNIT_EXTERNAL_ID = "UNIT-DEPT-FIN"


class SyncOrgStructureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provider = get_organization_provider()
        cls.unit_count = len(cls.provider.get_org_units())

    def setUp(self):
        self.registrar = User.objects.create_user(
            username=REGISTRAR_EMAIL, email=REGISTRAR_EMAIL, password="pass"
        )
        self.supervisor = User.objects.create_user(
            username=SUPERVISOR_EMAIL, email=SUPERVISOR_EMAIL, password="pass"
        )
        self.admin = User.objects.create_user(
            username=ADMIN_EMAIL, email=ADMIN_EMAIL, password="pass"
        )
        self.employee_one = User.objects.create_user(
            username="employee1@test.luanar",
            email="employee1@test.luanar",
            password="pass",
        )

    def test_first_run_creates_every_unit(self):
        summary = sync_org_structure_from_provider(self.provider)

        self.assertEqual(OrgUnit.objects.count(), self.unit_count)
        self.assertEqual(summary["created"], self.unit_count)
        self.assertEqual(summary["updated"], 0)

    def test_second_run_updates_in_place_without_duplicates(self):
        sync_org_structure_from_provider(self.provider)

        summary = sync_org_structure_from_provider(self.provider)

        self.assertEqual(OrgUnit.objects.count(), self.unit_count)
        self.assertEqual(summary["created"], 0)
        self.assertEqual(summary["updated"], self.unit_count)

    def test_second_run_restores_edited_fields_from_the_provider(self):
        sync_org_structure_from_provider(self.provider)
        unit = OrgUnit.objects.get(external_id="UNIT-CAMP-N")
        unit.name = "Renamed by hand"
        unit.save(update_fields=["name"])

        sync_org_structure_from_provider(self.provider)

        unit.refresh_from_db()
        self.assertEqual(unit.name, "Placeholder North Campus")

    def test_parents_and_flags_are_synced(self):
        sync_org_structure_from_provider(self.provider)

        institution = OrgUnit.objects.get(external_id="UNIT-INST")
        campus = OrgUnit.objects.get(external_id="UNIT-CAMP-N")
        department = OrgUnit.objects.get(external_id="UNIT-DEPT-MATH")
        registry = OrgUnit.objects.get(external_id="UNIT-DEPT-REG")
        team = OrgUnit.objects.get(external_id="UNIT-TEAM-REC")

        self.assertIsNone(institution.parent)
        self.assertEqual(campus.parent, institution)
        self.assertEqual(department.parent, OrgUnit.objects.get(
            external_id="UNIT-FAC-SCI"
        ))
        self.assertTrue(registry.has_teams)
        self.assertFalse(team.has_teams)

    def test_role_holders_resolve_to_local_users_by_email(self):
        sync_org_structure_from_provider(self.provider)

        campus = OrgUnit.objects.get(external_id="UNIT-CAMP-N")
        mathematics = OrgUnit.objects.get(external_id="UNIT-DEPT-MATH")
        physics = OrgUnit.objects.get(external_id="UNIT-DEPT-PHYS")
        team = OrgUnit.objects.get(external_id="UNIT-TEAM-REC")

        self.assertEqual(campus.designated_approver, self.registrar)
        self.assertEqual(mathematics.designated_approver, self.supervisor)
        self.assertEqual(physics.designated_approver, self.admin)
        self.assertEqual(team.designated_approver, self.employee_one)

    def test_vacant_role_holder_clears_designated_approver(self):
        sync_org_structure_from_provider(self.provider)

        vacant = OrgUnit.objects.get(external_id=VACANT_UNIT_EXTERNAL_ID)

        self.assertIsNone(vacant.designated_approver)
        summary = sync_org_structure_from_provider(self.provider)
        self.assertGreater(summary["vacant"], 0)

    def test_unresolvable_employee_counts_as_vacant(self):
        # No local user carries any fixture address in this test, so no unit
        # may appoint anyone.
        User.objects.all().delete()

        summary = sync_org_structure_from_provider(self.provider)

        mathematics = OrgUnit.objects.get(external_id="UNIT-DEPT-MATH")
        self.assertIsNone(mathematics.designated_approver)
        self.assertEqual(summary["role_linked"], 0)

    def test_summary_counts_match_the_provider_dataset(self):
        summary = sync_org_structure_from_provider(self.provider)

        self.assertEqual(
            set(summary), {"created", "updated", "role_linked", "vacant"}
        )
        self.assertEqual(
            summary["role_linked"] + summary["vacant"],
            len(self.provider.get_role_holders()),
        )
