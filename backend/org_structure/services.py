"""Organisation-structure sync from the external data provider.

Mirrors the provider's org tree into :class:`~org.models.OrgUnit` rows keyed
by ``external_id``, and appoints each unit's ``designated_approver`` from the
provider's role holders. Employee identity is reconciled by email through
``directory.services`` (agreed at planning for refinement unit 05: the fixture
employees carry the seeded demo users' addresses, so no external-id column is
needed yet).
"""

from django.db import transaction

from directory.services import get_local_user_for_external_employee

from .models import OrgUnit


@transaction.atomic
def sync_org_structure_from_provider(provider) -> dict:
    """Mirror the provider's org units and role holders into ``OrgUnit``.

    Idempotent: units are matched on ``external_id`` and updated in place, so
    a second run changes nothing unless the provider's data changed. Units are
    created before parents are linked, so the provider's list order does not
    matter; a parent id the provider references but does not define resolves
    to no parent rather than failing the whole sync.

    A role holder with ``employee_id=None`` (vacant) or one whose employee
    cannot be reconciled to a local user clears ``designated_approver`` — the
    sync never points a unit at the wrong person. Where a unit has several
    role holders, the last one in the provider's list wins.

    Returns a summary dict: ``created``, ``updated``, ``role_linked``,
    ``vacant``.
    """
    records = list(provider.get_org_units())
    created = updated = 0
    units_by_external: dict[str, OrgUnit] = {}

    for record in records:
        unit, was_created = OrgUnit.objects.update_or_create(
            external_id=record.id,
            defaults={
                "unit_type": record.unit_type,
                "name": record.name,
                "has_teams": record.has_teams,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
        units_by_external[record.id] = unit

    for record in records:
        unit = units_by_external[record.id]
        parent = units_by_external.get(record.parent_id)
        if unit.parent_id != (parent.pk if parent else None):
            unit.parent = parent
            unit.save(update_fields=["parent"])

    role_linked = vacant = 0
    for holder in provider.get_role_holders():
        unit = units_by_external.get(holder.org_unit_id)
        if unit is None:
            continue
        user = (
            get_local_user_for_external_employee(holder.employee_id)
            if holder.employee_id
            else None
        )
        unit.designated_approver = user
        unit.save(update_fields=["designated_approver"])
        if user is None:
            vacant += 1
        else:
            role_linked += 1

    return {
        "created": created,
        "updated": updated,
        "role_linked": role_linked,
        "vacant": vacant,
    }
