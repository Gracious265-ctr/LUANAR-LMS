"""Workflow configuration: section sequencing and chain structure.

The write-side of a workflow's *steps* — validating an ordered section list and
rewriting the stored rows through :func:`replace_workflow_sections`. Section
identity across writes, the role-uniqueness rule (Unit 30), and the ``PROTECT``
guard that stops a step being removed out from under a live application all live
here, so the team form, the standalone workflow screen, and inline team creation
share one implementation rather than three that can drift.
"""

from dataclasses import dataclass

from django.db.models import F
from django.db.models.deletion import ProtectedError

from roles.models import ApproverRole
from roles.services import _lookup_stage_role, _resolve_stage_role
from chains.models import Section, Workflow
from chains.services._shared import StageSequenceError


def normalize_section_sequence(sections: list[dict]) -> list[dict]:
    """Validate and renumber a workflow's section list in approval order.

    A section names its approver role by ``code`` (``"hod"``) — that is the wire
    contract — or by primary key for convenience. Either way the value is
    resolved against :class:`~workflows.models.ApproverRole`, and the normalized
    payload carries the role's *code* so the sequence round-trips through the API
    without leaking database ids into saved forms.

    A role may **not** repeat across sections of one workflow (Unit 30). It
    could once, on the reasoning that one person can sit at several points in a
    chain — but a role appearing twice means the same capacity signing off twice
    at two different points, and ``section_workflow_role_unique`` now says so at
    the database too. Repeating the role across *different* workflows is still
    fine; the rule is per workflow, not global.

    Returns a list of ``{"name", "approver_role", "order"}``. Raises
    :class:`StageSequenceError` for an empty list, an unknown or inactive
    approver role, a role already used by another section in the same payload, a
    missing/blank name, or a missing/non-positive/duplicate order.
    """
    items = list(sections)
    if not items:
        raise StageSequenceError(
            "sections", "At least one approval section is required."
        )

    seen_orders: set[int] = set()
    seen_roles: dict[int, int] = {}
    normalized: list[dict] = []

    for index, item in enumerate(items):
        role = _section_role(item)
        if role is None:
            raise StageSequenceError(
                "approver_role", "Select a valid approver role.", index
            )
        role_row = role if isinstance(role, ApproverRole) else _resolve_stage_role(role)
        if role_row is None:
            raise StageSequenceError(
                "approver_role",
                "That approver role is missing or deactivated. Pick an active "
                "role, or reactivate the role in Roles.",
                index,
            )
        role = role_row

        name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
        name = (name or "").strip() if isinstance(name, str) else ""
        if not name:
            # Fall back to the role's own label so a saved workflow is never
            # nameless; HR still gets to say what the step is for.
            name = role.label

        order = item.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise StageSequenceError(
                "order", "Section order must be a positive whole number.", index
            )
        if order in seen_orders:
            raise StageSequenceError(
                "order", "Section order numbers must be unique within a workflow.", index
            )
        seen_orders.add(order)

        # The role check runs after the order check so the error a caller sees
        # for a payload that is wrong in both ways names the ordering problem
        # first, which is the one they have to fix to make progress.
        first_use = seen_roles.get(role.pk)
        if first_use is not None:
            raise StageSequenceError(
                "approver_role",
                f"The {role.label} role is already assigned to another stage in "
                "this workflow. A role can only be assigned to one stage per "
                "workflow — give this stage a different role, or remove the "
                f"other one (step {first_use + 1}).",
                index,
            )
        seen_roles[role.pk] = index

        normalized.append(
            {"name": name, "approver_role": role.code, "order": index + 1}
        )

    return normalized


@dataclass(frozen=True)
class ActivationIssue:
    """One reason an activation/scheduling submission was rejected.

    ``field`` is the API field the issue belongs to (``"effective_from"`` for a
    scope conflict, ``None`` for a missing approver role). ``message`` is the
    human-readable explanation.
    """

    field: str | None
    message: str


def _section_role(section) -> int | str | ApproverRole | None:
    """The approver role a section payload names, whether dict or model.

    Returns an :class:`ApproverRole`, its primary key, or its code, as named.
    ``None`` means the payload named nothing usable. The ambiguity is harmless
    because :func:`normalize_section_sequence` only ever needs to resolve the
    value against a role, and the choice of code-vs-pk is an input detail.
    """
    if isinstance(section, dict):
        value = section.get("approver_role")
    elif isinstance(getattr(section, "approver_role", None), ApproverRole):
        return section.approver_role
    else:
        value = getattr(section, "approver_role_id", None)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, ApproverRole)):
        return value
    if isinstance(value, str):
        return value.strip()
    return None


def missing_approver_roles(sections) -> list[str]:
    """Labels of section roles that cannot currently be used, in section order.

    Activation is a configuration check, so the only thing it can know about
    member availability without an applicant is whether the *role itself* is
    usable. A role that has been deactivated is reported; whether a given
    section actually has somebody who can act is resolved per applicant at
    submission time (invariant 12.7 still blocks that submission).
    """
    missing: list[str] = []
    seen: set[int] = set()
    for section in sections:
        role = _section_role(section)
        if role is None:
            continue
        if not isinstance(role, ApproverRole):
            role = _lookup_stage_role(role)
        if role is None:
            continue
        if role.pk in seen:
            continue
        seen.add(role.pk)
        if not role.is_active:
            missing.append(role.label)
    return missing


def replace_workflow_sections(workflow: Workflow, sections) -> list[Section]:
    """Rewrite a workflow's section sequence, preserving membership.

    A section is identified across writes by its ``(role, name)`` pair. A
    section whose pair still appears in the payload keeps its row, and so keeps
    its appointed approver: re-ordering the chain must not silently unstaff the
    people who can act for it.

    A section whose role **or** name changed is a different step and is
    rebuilt empty. Deliberately not carried over: a step that moved to a
    different approver role has a different authority, and quietly handing
    the old appointment to the new role would grant it without HR asking. The
    step shows up with nobody appointed, which is visible and fixable, and
    submission is refused until it is staffed.

    ``(workflow, order)`` is unique, so the write is sequenced to avoid
    colliding with itself: stale sections go first, survivors are parked
    beyond any real order, and only then is the final order applied.

    Lives here rather than on the workflow serializer so a team created with
    its chain inline goes through the *same* rules as a standalone workflow
    edit — one implementation, so the two paths cannot drift apart. Returns
    the resulting sections in approval order.
    """
    existing = list(
        workflow.sections.select_related("approver_role").prefetch_related("members")
    )
    by_identity = {(s.approver_role_id, s.name): s for s in existing}

    resolved: list[tuple[dict, ApproverRole]] = []
    for payload in normalize_section_sequence(sections):
        role = _resolve_stage_role(payload["approver_role"])
        if role is None:
            raise StageSequenceError(
                "approver_role",
                f"Approver role '{payload['approver_role']}' is missing or "
                "deactivated.",
            )
        resolved.append((payload, role))

    # ``(payload, role, survivor_pk)``. A non-``None`` survivor keeps its row
    # and its members; ``None`` means build the step fresh.
    plan: list[tuple[dict, ApproverRole, int | None]] = []
    claimed: set[int] = set()
    for payload, role in resolved:
        survivor = by_identity.get((role.pk, payload["name"]))
        if survivor is not None and survivor.pk not in claimed:
            claimed.add(survivor.pk)
            plan.append((payload, role, survivor.pk))
        else:
            # Either a genuinely new step, or the same role+name a second
            # time in one payload. Role uniqueness (Unit 30) means the second
            # cannot be the same *role*, so reaching here twice with one role
            # means the role changed between the two entries — the second needs
            # its own row rather than reusing the first.
            plan.append((payload, role, None))

    # 1. Drop the steps that are no longer in the payload. Their members
    #    cascade. Doing this first means their orders are free for reuse.
    #    A step an application is still sitting on cannot go: the application's
    #    stage points at it, so deleting it would strand that application with
    #    no approver and no way to say who used to hold the step. Reported as a
    #    validation error naming the step, not as a database integrity error.
    try:
        workflow.sections.exclude(pk__in=claimed).delete()
    except ProtectedError as exc:
        blocked_ids: set[int] = set()
        for protected in exc.protected_objects:
            # Django hands back the referencing rows, not the rows being
            # deleted, so the blocked steps are read back off the referrers.
            for field in ("section_ref", "section"):
                value = getattr(protected, f"{field}_id", None)
                if value is not None:
                    blocked_ids.add(value)
        blocked = Section.objects.filter(pk__in=blocked_ids)
        names = ", ".join(f'"{section.name}"' for section in blocked) or "a step"
        raise StageSequenceError(
            "sections",
            f"Cannot remove {names}: an application is still waiting on that "
            "step. Decide or withdraw those applications first, then change the "
            "steps.",
        ) from exc

    # 2. Park the survivors, so writing the new order cannot collide with a
    #    surviving section that is currently sitting on the target order.
    for _, _, survivor_pk in plan:
        if survivor_pk is not None:
            Section.objects.filter(pk=survivor_pk).update(order=F("order") + 1_000_000)

    # 3. Apply the final order, building the steps that have no row yet.
    for payload, role, survivor_pk in plan:
        if survivor_pk is not None:
            Section.objects.filter(pk=survivor_pk).update(order=payload["order"])
            continue
        Section.objects.create(
            workflow=workflow,
            name=payload["name"],
            approver_role=role,
            order=payload["order"],
        )

    return list(workflow.sections.select_related("approver_role").order_by("order"))


def _workflow_snapshot(workflow: Workflow) -> dict:
    """A workflow's chain, in role *codes* with its current open members.

    Codes rather than ids so the entry stays readable years after the role is
    renamed; the member list is the open memberships only, which is the roster
    the chain actually routes with.
    """
    return {
        "name": workflow.name,
        "effective_from": workflow.effective_from,
        "effective_to": workflow.effective_to,
        "is_active": workflow.is_active,
        "sections": [
            {
                "name": section.name,
                "order": section.order,
                "approver_role": section.approver_role.code,
                "approver": (
                    {
                        "user_id": section.approver_id,
                        "name": section.approver.get_full_name()
                        or section.approver.username,
                    }
                    if section.approver_id
                    else None
                ),
            }
            for section in workflow.sections.order_by("order").select_related(
                "approver_role"
            )
        ],
    }

def workflow_section_roles(workflow: Workflow) -> list[ApproverRole]:
    """The distinct roles a workflow's sections ask for, in first-seen order.

    A role may repeat across sections; the picker only needs to know which roles
    are in play, once each.
    """
    if workflow.pk is None:
        return []
    role_ids = list(
        workflow.sections.order_by("order")
        .values_list("approver_role", flat=True)
        .distinct()
    )
    if not role_ids:
        return []
    by_id = {
        role.pk: role
        for role in ApproverRole.objects.filter(pk__in=role_ids).select_related()
    }
    return [by_id[role_id] for role_id in role_ids if role_id in by_id]
