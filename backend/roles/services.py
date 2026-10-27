"""Organisation-owned approver, role, team-membership, and campus service layer.

Holds everything answering "who/what is this unit, who approves, and what is its
structure": approver-role administration, role assignments, team membership,
and campus administration, plus the approver-resolution helpers shared with the
workflow builder and the launcher.
"""

from dataclasses import dataclass
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify
from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from users.models import EmployeeProfile, User
from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment
from teams.models import Team, TeamRoleAssignment
from chains.models import Section, SectionMember, WorkflowMember


def _resolve_stage_role(value) -> ApproverRole | None:
    """Look up an *active* :class:`ApproverRole` by code or primary key."""
    role = _lookup_stage_role(value)
    return role if role is not None and role.is_active else None


def _lookup_stage_role(value) -> ApproverRole | None:
    """Look up an :class:`ApproverRole` by code or primary key, active or not.

    Callers that need to distinguish "deactivated" from "unknown" use this;
    callers that just need a usable role use :func:`_resolve_stage_role`.
    """
    if isinstance(value, ApproverRole):
        return value
    if isinstance(value, str) and not value.strip().isdigit():
        return ApproverRole.objects.filter(code=value).first()
    try:
        pk = int(value)
    except (TypeError, ValueError):
        return None
    return ApproverRole.objects.filter(pk=pk).first()


def is_approver_user(user) -> bool:
    """Whether ``user`` currently holds at least one active approver role.

    The one and only definition of "is an approver", replacing every former
    role-name check. A person is an approver when they can act for at least one
    section whose :class:`~workflows.models.ApproverRole` is active, or when
    they hold a wide holding of an active role:

    * a :class:`~workflows.models.SectionMember` row, or
    * a :class:`~workflows.models.TeamRoleAssignment` row (team-wide), or
    * a :class:`~workflows.models.CampusRoleAssignment` row (campus-wide), or
    * a :class:`~workflows.models.RoleAssignment` row (institution-wide).

    The wide holdings belong here for the same reason the section roster does:
    they are what *resolves* a stage, so a campus registrar whose team's chain
    names their role with no local appointment is an approver in every sense
    that matters — they just never appears on a section.

    Deactivating a role therefore retires the approver status it conferred, and
    ``User.role`` is irrelevant: it records system access, not a place in an
    approval chain.
    """
    if not user or not getattr(user, "is_active", False):
        return False
    user_id = user.pk if hasattr(user, "pk") else user
    if user_id is None:
        return False
    if SectionMember.objects.effective_on().filter(
        user_id=user_id, section__approver_role__is_active=True
    ).exists():
        return True
    if TeamRoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists():
        return True
    if CampusRoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists():
        return True
    return RoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists()


def is_hr_actor(actor) -> bool:
    """Whether ``actor`` is HR or a superuser — the unrestricted team role."""
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and (
            getattr(actor, "role", None) == User.Role.HR
            or getattr(actor, "is_superuser", False)
        )
    )


def is_team_manager(user, team: Team | None) -> bool:
    """Whether ``user`` is the designated manager of ``team``.

    A team's manager is the one team-wide holder flagged
    :attr:`~workflows.models.TeamRoleAssignment.is_team_manager`. Only that
    person — not every wide holder — is authorised to manage the team's members
    and workflows, so management is scoped to a single designated approver.
    """
    if team is None or not getattr(user, "is_authenticated", False):
        return False
    return TeamRoleAssignment.objects.filter(
        team=team, user=user, is_team_manager=True, role__is_active=True
    ).exists()


def managed_team_ids_for(user) -> list[int]:
    """The ids of the teams ``user`` is the designated manager of.

    The queryset sibling of :func:`is_team_manager`, for the callers that ask
    the question about the *user* rather than about one team: the launcher's
    access gate ("may this account open the module?") and the sidebar's "My
    Team" entry ("show the way in?"). Both need the whole set at once, and both
    must agree with the per-team guard, so the definition lives here alone.
    Sorted so the answer is stable between reads.
    """
    if not getattr(user, "is_authenticated", False):
        return []
    return list(
        TeamRoleAssignment.objects.filter(
            user=user, is_team_manager=True, role__is_active=True
        )
        .order_by("team_id")
        .values_list("team_id", flat=True)
        .distinct()
    )


def _require_hr_actor(actor, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR: the identity/lifecycle guard."""
    if is_hr_actor(actor):
        return
    raise error_cls("detail", "Only HR may perform this action.")


def approver_role_codes_for(user) -> list[str]:
    """The active approver-role codes ``user`` holds, de-duplicated and sorted.

    Sorted rather than ranked so the answer is stable: a person holding several
    roles is described the same way on every request, which matters for surfaces
    that render a single role label (the delegation list) and for API payloads
    that should not reshuffle between reads.
    """
    if not user or not getattr(user, "is_active", False):
        return []
    user_id = user.pk if hasattr(user, "pk") else user
    codes = set(
        SectionMember.objects.effective_on()
        .filter(user_id=user_id, section__approver_role__is_active=True)
        .values_list("section__approver_role__code", flat=True)
    )
    codes.update(
        RoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    codes.update(
        TeamRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    codes.update(
        CampusRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    return sorted(code for code in codes if code)


def approver_role_labels_for(user) -> list[str]:
    """The active approver-role labels ``user`` holds, in a stable order.

    Used by HR surfaces (the delegate candidate list) so a person is described by
    the roles they actually hold rather than by a system access level.
    """
    if not user or not getattr(user, "is_active", False):
        return []
    user_id = user.pk if hasattr(user, "pk") else user
    labels = set(
        SectionMember.objects.effective_on()
        .filter(user_id=user_id, section__approver_role__is_active=True)
        .values_list("section__approver_role__label", flat=True)
    )
    labels.update(
        RoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    labels.update(
        TeamRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    labels.update(
        CampusRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    return sorted(label for label in labels if label)


class RoleActionError(ValueError):
    """Raised when an approver-role write cannot be applied.

    ``field`` is the API field the error belongs to (``"detail"`` when the
    problem is the role's state rather than one submitted value).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def role_usage_map(roles) -> dict[int, list[str]]:
    """``_role_usage`` for a whole queryset, in a fixed number of queries.

    The Roles screen renders usage for every role at once, and the naive
    per-role version cost one query per blocker per role — 69 queries to
    serialize six roles, and worse as HR adds more. Collecting each blocker
    kind for all roles at once and assembling the sentences in Python makes the
    list cost three queries no matter how many roles it holds.
    """
    role_ids = {role.pk for role in roles}
    usage: dict[int, list[str]] = {pk: [] for pk in role_ids}
    if not role_ids:
        return usage

    # A section and its members are one blocker from HR's point of view: the
    # workflow uses this role. Grouping by workflow and merging into a single
    # clause avoids telling HR the same workflow is a problem twice.
    section_rows = (
        Section.objects.filter(
            approver_role_id__in=role_ids,
            workflow__is_active=True,
            is_active=True,
        )
        .values("approver_role_id", "workflow_id", "workflow__name")
        .annotate(count=Count("id"))
        .order_by("workflow__name", "workflow_id")
    )
    section_counts: dict[tuple[int, str], int] = {}
    workflow_names: dict[tuple[int, str], str] = {}
    for row in section_rows:
        key = (row["approver_role_id"], row["workflow_id"])
        section_counts[key] = row["count"]
        workflow_names[key] = row["workflow__name"]

    member_rows = (
        SectionMember.objects.filter(
            section__approver_role_id__in=role_ids,
            section__is_active=True,
            section__workflow__is_active=True,
        )
        .values(
            "section__approver_role_id",
            "section__workflow_id",
        )
        .annotate(count=Count("id"))
    )
    member_counts: dict[tuple[int, str], int] = {
        (row["section__approver_role_id"], row["section__workflow_id"]): row["count"]
        for row in member_rows
    }

    for key, section_total in section_counts.items():
        parts = [f"{section_total} section" + ("" if section_total == 1 else "s")]
        members = member_counts.get(key, 0)
        if members:
            parts.append(f"{members} member" + ("" if members == 1 else "s"))
        usage[key[0]].append(
            f"the '{workflow_names[key]}' workflow ({' and '.join(parts)})"
        )

    holders = (
        RoleAssignment.objects.filter(role_id__in=role_ids, user__is_active=True)
        .select_related("user")
        .order_by("user_id")
    )
    for assignment in holders:
        name = assignment.user.get_full_name() or assignment.user.username
        usage[assignment.role_id].append(f"{name}, who holds it institution-wide")

    return usage


def _role_usage(role: ApproverRole) -> list[str]:
    """Human-readable sentences naming everything currently using ``role``.

    Each clause names the specific blocker and its size, so a refused
    deactivation tells HR exactly which workflows, teams, and people to fix
    instead of just saying "in use".
    """
    return role_usage_map([role]).get(role.pk, [])


def ensure_role_not_in_use(role: ApproverRole) -> None:
    """Refuse while an active workflow stage, team member, or holder uses the role."""
    clauses = _role_usage(role)
    if not clauses:
        return
    raise RoleActionError(
        "detail",
        f"This role cannot be deactivated because it is used by "
        f"{', and by '.join(clauses)}. Remove those references first, or "
        "deactivate the workflow or team instead.",
    )


def role_code_from_name(name: object) -> str:
    """Derive a role's stable code from its name, uniquely.

    The code is what a workflow stage keys off and what historical stage
    snapshots quote, so it has to exist and has to be unique — but asking HR to
    type one alongside the name is asking for the same word twice, and for the
    two to disagree. Deriving it removes that class of mistake entirely.

    Uniqueness is checked against the table rather than assumed, because
    slugifying two different names ("Head of Department" and "Head of
    Departments") gives the same code.
    """
    cleaned = (name or "").strip() if isinstance(name, str) else ""
    if not cleaned:
        raise RoleActionError("label", "Enter a role name.")
    base = slugify(cleaned)
    if not base:
        raise RoleActionError(
            "label",
            "The role name must contain a letter or number to form its code.",
        )
    code = base[:50]
    suffix = 2
    while ApproverRole.objects.filter(code=code).exists():
        tail = f"-{suffix}"
        code = f"{base[: 50 - len(tail)]}{tail}"
        suffix += 1
    return code


def create_approver_role(*, actor, data: dict) -> tuple[ApproverRole, bool]:
    """Create one approver role from its name, or return the one that has it.

    Only the name is HR's to give. ``code`` is derived from it (see
    :func:`role_code_from_name`), and the behavioural fields — history scope,
    cancellation handling, institution-wide eligibility — are left at their
    defaults and changed later through the role's own edit, by somebody who has
    the context to decide them.

    Deriving rather than asking is what keeps a role from existing in two
    incompatible states: a name that says "Vice Chancellor" beside a code that
    says ``vc``, where the label is what every screen shows and the code is what
    every rule reads.

    A name that already names a role does **not** create a second one: the same
    word typed twice — by HR on the Roles screen, or by a team manager from the
    chain form's "New role" card — resolves to the role that already exists.
    Two offices sharing a name is exactly the ambiguity a chain cannot afford,
    and the caller only ever meant "the Registrar", not "a second Registrar".
    Matching is on the label, case- and whitespace-insensitively, because that
    is the name people type; two *different* labels that happen to slug alike
    are still two roles and keep separate codes.

    Returns ``(role, created)``. ``created`` is False when an existing role was
    reused, so the API can answer 200 rather than 201 and the caller can say
    "already exists" without guessing. A matching *retired* role is refused
    instead of silently reused: past stages still quote its name, and bringing
    it back is HR's decision, not a side effect of adding a step.
    """
    data = dict(data)
    label = (data.get("label") or "").strip()
    if not label:
        raise RoleActionError("label", "Enter a role name.")
    existing = (
        ApproverRole.objects.filter(label__iexact=label).order_by("pk").first()
    )
    if existing is not None:
        if not existing.is_active:
            raise RoleActionError(
                "label",
                f"The {existing.label} role already exists but is retired. Ask HR "
                "to reactivate it in Roles.",
            )
        return existing, False
    data["label"] = label
    data["code"] = role_code_from_name(label)
    for field in (
        "history_scope",
        "handles_cancellation",
        "is_institution_wide",
        "is_active",
    ):
        data.pop(field, None)
    with transaction.atomic():
        role = ApproverRole.objects.create(**data)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail={"before": None, "after": _role_snapshot(role)},
        )
    return role, True


def update_approver_role(*, role: ApproverRole, actor, data: dict) -> ApproverRole:
    """Update a role's editable fields and audit the change.

    ``code`` is immutable once anything references the role, because workflow
    stages, team members, and historical stage snapshots all key off it; HR
    edits ``label``, ``description``, ``history_scope``, and
    ``handles_cancellation`` here. ``is_institution_wide`` is deliberately not
    one of them: a role's scope is decided by where it is held, on the Approvers
    page — it becomes institution-wide the moment its first institution-wide
    holder is assigned, not from a checkbox on this screen.

    ``is_active`` is deliberately *not* handled here: retiring a role runs the
    in-use check, so it has its own action.
    """
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        before = _role_snapshot(role)
        if "code" in data and data["code"] != before["code"]:
            raise RoleActionError(
                "code",
                "The role code cannot be changed once the role is referenced by a "
                "workflow stage, a team member, or a role assignment. Create a new "
                "role instead and retire this one.",
            )
        data.pop("code", None)
        data.pop("is_active", None)
        if (
            data.get("is_institution_wide", before["is_institution_wide"])
            != before["is_institution_wide"]
        ):
            raise RoleActionError(
                "is_institution_wide",
                "A role's scope is decided on the Approvers page: the role "
                "becomes institution-wide when its first institution-wide holder "
                "is assigned there. It is not toggled from the role itself.",
            )
        data.pop("is_institution_wide", None)
        for field, value in data.items():
            setattr(role, field, value)
        role.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(before, _role_snapshot(role)),
        )
    return role


def deactivate_approver_role(*, role: ApproverRole, actor) -> ApproverRole:
    """Soft-retire a role, refusing while anything still uses it."""
    if not role.is_active:
        return role
    ensure_role_not_in_use(role)
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        if not role.is_active:
            return role
        ensure_role_not_in_use(role)
        before = _role_snapshot(role)
        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(before, _role_snapshot(role)),
            reason="Role deactivated by HR.",
        )
    return role


def _role_snapshot(role: ApproverRole) -> dict:
    return {
        "code": role.code,
        "label": role.label,
        "description": role.description,
        "is_active": role.is_active,
        "history_scope": role.history_scope,
        "handles_cancellation": role.handles_cancellation,
        "is_institution_wide": role.is_institution_wide,
    }


def _repoint_wide_positions(
    *,
    role: ApproverRole,
    previous_user: User,
    new_user: User,
    team: Team | None = None,
    campus: Campus | None = None,
) -> None:
    """Move the positions a replaced wide approver held onto their successor.

    A wide approver's holding staffs chains within its scope — the steps that
    name the role, and the chains they were placed on as a normal member. When
    the holding is re-pointed at a new person, the successor inherits those
    positions rather than leaving every step and membership pointing at somebody
    who no longer holds the role.

    Only the positions the outgoing holder actually had are moved, and only
    within the holding's scope:

    * ``team`` scopes the move to that team's chains (a team-wide holding);
    * ``campus`` scopes it to the teams at that campus (a campus-wide holding);
    * neither scopes it to every team (an institution-wide holding).

    A step is moved only when it names this role *and* pointed at the outgoing
    holder, so a step HR gave to somebody else by hand is left alone. Each
    handover closes the outgoing holder's :class:`SectionMember` period and opens
    the successor's, exactly as :func:`chains.services.add_section_member`
    does, so "who held the step in March" stays answerable. A wide membership the
    successor already has on the same workflow is not duplicated — the outgoing
    row is simply dropped.
    """
    sections = Section.objects.filter(approver_role=role, approver=previous_user)
    if team is not None:
        sections = sections.filter(workflow__team=team)
    if campus is not None:
        sections = sections.filter(workflow__team__campus=campus)

    today = timezone.localdate()
    for section in sections:
        SectionMember.objects.filter(
            section=section, user=previous_user, effective_to__isnull=True
        ).update(effective_to=today)
        section.approver = new_user
        section.save(update_fields=["approver"])
        membership = SectionMember(
            section=section, user=new_user, effective_from=today
        )
        membership.full_clean()
        membership.save()

    memberships = WorkflowMember.objects.filter(
        user=previous_user, is_wide_approver=True
    )
    if team is not None:
        memberships = memberships.filter(team=team)
    if campus is not None:
        memberships = memberships.filter(team__campus=campus)
    for membership in memberships:
        clash = WorkflowMember.objects.filter(
            workflow=membership.workflow, user=new_user
        ).exists()
        if clash:
            membership.delete()
        else:
            membership.user = new_user
            membership.save(update_fields=["user"])


def replace_role_assignment(
    *, assignment: RoleAssignment, user: User, actor
) -> RoleAssignment:
    """Hand an institution-wide holding to a new person, positions and all.

    A role has exactly one institution-wide holder, so changing it is a replace
    rather than a remove-then-assign: this re-points the holding at ``user`` and
    moves every step and wide membership the outgoing holder staffed under the
    role onto them in the same atomic step. Without it a chain written while the
    old holder was in post would keep routing to somebody who no longer holds
    the role.

    Refuses an inactive user, and refuses the holder they already are.
    """
    with transaction.atomic():
        assignment = RoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        role = assignment.role
        if not user.is_active:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before assigning a role.",
            )
        if assignment.user_id == user.pk:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} already holds the "
                f"{role.label} role institution-wide.",
            )
        outgoing = assignment.user
        before = {
            "user_id": outgoing.pk,
            "user": outgoing.get_full_name() or outgoing.username,
            "assignment_id": assignment.pk,
        }
        assignment.user = user
        assignment.save(update_fields=["user"])
        _repoint_wide_positions(
            role=role, previous_user=outgoing, new_user=user
        )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(
                before,
                {
                    "user_id": user.pk,
                    "user": user.get_full_name() or user.username,
                    "assignment_id": assignment.pk,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} now holds the "
                f"{role.label} role institution-wide, replacing "
                f"{outgoing.get_full_name() or outgoing.username}."
            ),
        )
    return assignment


def create_role_assignment(*, user: User, role: ApproverRole, actor) -> RoleAssignment:
    """Assign an institution-wide role to a user and audit it.

    The first institution-wide holder is what *makes* a role institution-wide:
    assigning holder number one to a team role on the Approvers page is the
    decision that the role covers every application — not a checkbox on the
    role's own editor (which no longer offers one). The role is promoted in the
    same atomic step as the holding, and the promotion is refused only while the
    role is still held on a team or campus, because a role cannot be held wide
    at a scope *and* institution-wide at once.

    A role has exactly one institution-wide approver: once a holding exists this
    single write is refused for any other person, naming the current holder. A
    role is never assigned to a second approver — changing who holds it is a
    remove first, then a fresh assignment.
    """
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        role.full_clean(exclude=["code", "label"])
        if not role.is_active:
            raise RoleActionError(
                "role",
                f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
                "an active role.",
            )
        if not role.is_institution_wide:
            if (
                TeamRoleAssignment.objects.filter(role=role).exists()
                or CampusRoleAssignment.objects.filter(role=role).exists()
            ):
                raise RoleActionError(
                    "role",
                    f'"{role.label}" is already held on a team or campus. Remove '
                    "those holders under Approvers first — a role held wide at a "
                    "team or campus cannot be held institution-wide too.",
                )
            before = _role_snapshot(role)
            role.is_institution_wide = True
            role.save(update_fields=["is_institution_wide", "updated_at"])
            record_audit(
                actor=actor,
                action=AuditEntry.Action.UPDATED,
                target_type=AuditEntry.TargetType.APPROVER_ROLE,
                target_id=role.pk,
                target_summary=role.label,
                detail=changed_fields(before, _role_snapshot(role)),
                reason=(
                    f'"{role.label}" named institution-wide by its first '
                    "institution-wide holder on the Approvers page."
                ),
            )
        if not user.is_active:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before assigning a role.",
            )
        current_holder = (
            RoleAssignment.objects.select_for_update().filter(role=role).first()
        )
        if current_holder is not None and current_holder.user_id != user.pk:
            raise RoleActionError(
                "role",
                f'"{role.label}" is already held institution-wide by '
                f"{current_holder.user.get_full_name() or current_holder.user.username}. "
                "A role has one institution-wide approver; remove that holder under "
                "Approvers first, then assign another.",
            )
        _ensure_single_wide_holding(user, exclude_role=role)
        assignment, created = RoleAssignment.objects.get_or_create(
            user=user, role=role
        )
        if not created:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} already holds the "
                f"{role.label} role.",
            )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(
                {},
                {
                    "user_id": user.pk,
                    "user": user.get_full_name() or user.username,
                    "assignment_id": assignment.pk,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} assigned the "
                f"{role.label} role institution-wide."
            ),
        )
    return assignment


def remove_role_assignment(*, assignment: RoleAssignment, actor) -> RoleAssignment:
    """Remove an institution-wide role holding and audit it."""
    with transaction.atomic():
        user = assignment.user
        role = assignment.role
        detail = changed_fields(
            {
                "user_id": user.pk,
                "user": user.get_full_name() or user.username,
                "assignment_id": assignment.pk,
            },
            {},
        )
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=detail,
            reason=(
                f"{user.get_full_name() or user.username} no longer holds the "
                f"{role.label} role."
            ),
        )
    return assignment


def create_team_role_assignment(
    *, team: Team, role: ApproverRole, user: User, actor, is_team_manager: bool = False
) -> TeamRoleAssignment:
    """Give a role one team-wide holder, replacing any existing one.

    One holder per role per team is a constraint rather than a default: a team
    whose role has two wide holders would resolve a stage to a person nobody
    can name, and the resolution rule refuses ties anyway. So writing a second
    holder *is* the replacement — HR picks the role and the person in one
    screen, and saving it moves the holding rather than asking for a delete
    first.

    Refuses an institution-wide role (that holding lives under Approvers), a
    retired role, and a holder whose category does not match the team's, and
    audits both the appointment and the replacement.

    ``is_team_manager`` designates the holder as the team's single designated
    manager, clearing the flag from any other holder on the team. When a role
    that already carries the manager flag is re-pointed at a new person, the
    new person inherits it — the designation belongs to the role holding, not
    to the person who used to hold it.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        _ensure_wide_role(role, user, "team")
        profile = user.employee_profile
        if profile.category != team.category:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is an "
                f"{profile.get_category_display()} employee, but \"{team.name}\" "
                f"is an {team.get_category_display()} team. A team-wide approver "
                f"must match the team's category.",
            )
        _ensure_single_wide_holding(user, exclude_role=role, exclude_team=team)
        previous = (
            TeamRoleAssignment.objects.select_for_update()
            .filter(team=team, role=role)
            .first()
        )
        # A role that already carries the manager flag keeps it when it is
        # re-pointed: the designation follows the role holding.
        if previous is not None and previous.is_team_manager:
            is_team_manager = True
        if is_team_manager:
            # Enforce "one manager per team" *before* this holding is written,
            # so the partial unique constraint is never momentarily violated:
            # every other holder on the team has the flag cleared first.
            others = TeamRoleAssignment.objects.select_for_update().filter(
                team=team, is_team_manager=True
            )
            if previous is not None:
                others = others.exclude(pk=previous.pk)
            others.update(is_team_manager=False)
        before = None
        if previous is not None:
            if previous.user_id == user.pk:
                raise RoleActionError(
                    "user",
                    f"{user.get_full_name() or user.username} already holds the "
                    f"{role.label} role on {team.name}.",
                )
            before = _team_assignment_snapshot(previous)
            outgoing = previous.user
            previous.user = user
            previous.is_team_manager = is_team_manager
            previous.save(update_fields=["user", "is_team_manager"])
            assignment = previous
            _repoint_wide_positions(
                role=role,
                previous_user=outgoing,
                new_user=user,
                team=team,
            )
        else:
            assignment = TeamRoleAssignment.objects.create(
                team=team, role=role, user=user, is_team_manager=is_team_manager
            )
        record_audit(
            actor=actor,
            action=(
                AuditEntry.Action.UPDATED
                if before is not None
                else AuditEntry.Action.CREATED
            ),
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(
                before or {},
                _team_assignment_snapshot(assignment),
            ),
            reason=(
                f"{user.get_full_name() or user.username} holds {role.label} "
                f"for the {team.name} team."
                + (
                    " Designated as team manager."
                    if assignment.is_team_manager
                    else ""
                )
            ),
        )
    return assignment


def set_team_manager(*, assignment: TeamRoleAssignment, actor) -> TeamRoleAssignment:
    """Designate a team-wide holding as its team's manager.

    Clears the flag from any other holder on the same team, so a team always
    has at most one manager. A no-op when this holding is already the manager.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        locked = TeamRoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if locked.is_team_manager:
            return locked
        before = _team_assignment_snapshot(locked)
        # Clear the flag from the other holders first, so the partial unique
        # constraint ("one manager per team") is never momentarily violated.
        TeamRoleAssignment.objects.select_for_update().filter(
            team_id=locked.team_id, is_team_manager=True
        ).exclude(pk=locked.pk).update(is_team_manager=False)
        locked.is_team_manager = True
        locked.save(update_fields=["is_team_manager"])
        team = locked.team
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_assignment_snapshot(locked)),
            reason=(
                f"{locked.user.get_full_name() or locked.user.username} is the "
                f"team manager for {team.name}."
            ),
        )
    return locked


def clear_team_manager(*, assignment: TeamRoleAssignment, actor) -> TeamRoleAssignment:
    """Remove the manager designation from a team-wide holding.

    A no-op when the holding was not the manager.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        locked = TeamRoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if not locked.is_team_manager:
            return locked
        before = _team_assignment_snapshot(locked)
        locked.is_team_manager = False
        locked.save(update_fields=["is_team_manager"])
        team = locked.team
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_assignment_snapshot(locked)),
            reason=(
                f"{locked.user.get_full_name() or locked.user.username} is no "
                f"longer the team manager for {team.name}."
            ),
        )
    return locked


def remove_team_role_assignment(*, assignment: TeamRoleAssignment, actor) -> None:
    """Drop a team-wide holding and audit it."""
    with transaction.atomic():
        team = assignment.team
        role = assignment.role
        detail = changed_fields(_team_assignment_snapshot(assignment), {})
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=detail,
            reason=f"{role.label} no longer has a team-wide holder on {team.name}.",
        )


def create_campus_role_assignment(
    *, campus: Campus, role: ApproverRole, user: User, actor
) -> CampusRoleAssignment:
    """Give a role one campus-wide holder, replacing any existing one.

    Scoped to the campus, which is what makes it apply to every team *at* that
    campus and to no team anywhere else. Same one-holder rule and same
    replacement semantics as the team-wide holding.

    Every team at a campus is an academic team — an administration team is never
    campus-based — so the holder is refused unless they are an Academic
    employee.
    """
    with transaction.atomic():
        _ensure_wide_role(role, user, "campus")
        profile = user.employee_profile
        if profile.category != EmployeeProfile.Category.ACADEMIC:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is an "
                f"{profile.get_category_display()} employee. Every team at a "
                f"campus is an academic team, so a campus-wide approver must be "
                f"an Academic employee.",
            )
        _ensure_single_wide_holding(user, exclude_role=role, exclude_campus=campus)
        previous = (
            CampusRoleAssignment.objects.select_for_update()
            .filter(campus=campus, role=role)
            .first()
        )
        before = None
        if previous is not None:
            if previous.user_id == user.pk:
                raise RoleActionError(
                    "user",
                    f"{user.get_full_name() or user.username} already holds the "
                    f"{role.label} role at {campus.name}.",
                )
            before = _campus_assignment_snapshot(previous)
            outgoing = previous.user
            previous.user = user
            previous.save(update_fields=["user"])
            assignment = previous
            _repoint_wide_positions(
                role=role,
                previous_user=outgoing,
                new_user=user,
                campus=campus,
            )
        else:
            assignment = CampusRoleAssignment.objects.create(
                campus=campus, role=role, user=user
            )
        record_audit(
            actor=actor,
            action=(
                AuditEntry.Action.UPDATED
                if before is not None
                else AuditEntry.Action.CREATED
            ),
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=changed_fields(
                before or {},
                _campus_assignment_snapshot(assignment),
            ),
            reason=(
                f"{user.get_full_name() or user.username} holds {role.label} "
                f"at {campus.name}."
            ),
        )
    return assignment


def remove_campus_role_assignment(*, assignment: CampusRoleAssignment, actor) -> None:
    """Drop a campus-wide holding and audit it."""
    with transaction.atomic():
        campus = assignment.campus
        role = assignment.role
        detail = changed_fields(_campus_assignment_snapshot(assignment), {})
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=detail,
            reason=f"{role.label} no longer has a holder at {campus.name}.",
        )


def _ensure_wide_role(role: ApproverRole, user: User, scope: str) -> None:
    """The shared preconditions of a team- or campus-wide holding."""
    scope_label = "team" if scope == "team" else "campus"
    if not role.is_active:
        raise RoleActionError(
            "role",
            f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
            "an active role.",
        )
    if role.is_institution_wide:
        raise RoleActionError(
            "role",
            f'"{role.label}" is an institution-wide role. Assign its holder '
            "under Approvers, not on a "
            f"{scope_label}.",
        )
    if not user.is_active:
        raise RoleActionError(
            "user",
            f"{user.get_full_name() or user.username} is not an active user. "
            "Activate the account before assigning a role.",
        )
    if getattr(user, "employee_profile", None) is None:
        raise RoleActionError(
            "user",
            f"{user.get_full_name() or user.username} has no employee record, so "
            "there is nothing to hold an approver role with. Complete their "
            "employee record first.",
        )


def _ensure_single_wide_holding(
    user: User,
    *,
    exclude_role: ApproverRole | None = None,
    exclude_team: Team | None = None,
    exclude_campus: Campus | None = None,
) -> None:
    """Refuse a person a second wide approver role, anywhere in the school.

    A wide approver is someone a whole scope falls back to, and HR changes them
    per role per scope; one person covering a role on one team, a role at one
    campus, *and* a role institution-wide means three sections claim the same
    person, and a role written onto a team page is how somebody keeps appearing
    in the other sections' pickers. So a person holds **one** wide approver role,
    at one of the three scopes — which is also the promise the pickers make:
    once assigned, somebody is gone from every other wide-approver section.

    The exclusions name the (scope, role) pair this write is replacing: the same
    role at the same scope is that write's own target (already its holder, or
    about to be), not a second holding, so a save can still re-point a holding
    in place.
    """
    holdings = RoleAssignment.objects.filter(user=user)
    if exclude_role is not None:
        holdings = holdings.exclude(role=exclude_role)
    holding = holdings.select_related("role").first()
    if holding is not None:
        where = f"{holding.role.label} institution-wide"
    else:
        team_holdings = TeamRoleAssignment.objects.filter(user=user)
        if exclude_team is not None and exclude_role is not None:
            team_holdings = team_holdings.exclude(team=exclude_team, role=exclude_role)
        holding = team_holdings.select_related("role", "team").first()
        if holding is not None:
            where = f"{holding.role.label} as a team-wide approver on {holding.team.name}"
        else:
            campus_holdings = CampusRoleAssignment.objects.filter(user=user)
            if exclude_campus is not None and exclude_role is not None:
                campus_holdings = campus_holdings.exclude(
                    campus=exclude_campus, role=exclude_role
                )
            holding = campus_holdings.select_related("role", "campus").first()
            if holding is not None:
                where = f"{holding.role.label} as a campus-wide approver at {holding.campus.name}"
            else:
                where = None
    if where is not None:
        raise RoleActionError(
            "user",
            f"A person may hold only one wide approver role, and "
            f"{user.get_full_name() or user.username} already holds {where}. "
            f"Remove that holding before assigning another one.",
        )


def _team_assignment_snapshot(assignment: TeamRoleAssignment) -> dict:
    return {
        "assignment_id": assignment.pk,
        "role_id": assignment.role_id,
        "role": assignment.role.label,
        "user_id": assignment.user_id,
        "user": assignment.user.get_full_name() or assignment.user.username,
        "is_team_manager": assignment.is_team_manager,
    }


def _campus_assignment_snapshot(assignment: CampusRoleAssignment) -> dict:
    return {
        "assignment_id": assignment.pk,
        "role_id": assignment.role_id,
        "role": assignment.role.label,
        "user_id": assignment.user_id,
        "user": assignment.user.get_full_name() or assignment.user.username,
    }


class CampusActionError(ValueError):
    """Raised when a campus write cannot be applied."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def _campus_snapshot(campus: Campus) -> dict:
    return {
        "name": campus.name,
        "code": campus.code,
        "is_active": campus.is_active,
    }


def create_campus(*, actor, data: dict) -> Campus:
    """Create a campus and audit it."""
    with transaction.atomic():
        campus = Campus.objects.create(**data)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail={"before": None, "after": _campus_snapshot(campus)},
        )
    return campus


def update_campus(*, campus: Campus, actor, data: dict) -> Campus:
    """Update a campus and audit the change.

    A campus is PROTECTed from deletion because a team references it, and its
    code is treated like a role's: once referenced, changing it would leave a
    team pointing at a code nobody recognises.
    """
    with transaction.atomic():
        campus = Campus.objects.select_for_update().get(pk=campus.pk)
        before = _campus_snapshot(campus)
        if "code" in data and data["code"] != before["code"]:
            if campus.teams.exists():
                raise CampusActionError(
                    "code",
                    "The campus code cannot be changed once a team uses it. "
                    "Create a new campus instead.",
                )
        for field, value in data.items():
            setattr(campus, field, value)
        campus.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=changed_fields(before, _campus_snapshot(campus)),
        )
    return campus


class WorkflowMemberError(ValueError):
    """Raised when a team-member or workflow-member write cannot be applied.

    ``field`` is the API field the error belongs to, matching
    :class:`TeamActionError` so viewsets can map both the same way.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def _member_display_name(user: User) -> str:
    return user.get_full_name() or user.username


def wide_approver_ids_for_team(team: Team | None) -> set[int]:
    """User ids who are wide approvers for ``team``.

    A wide approver staffs a chain without being appointed to its steps: the
    holder of a team-wide role on this team, the holder of a campus-wide role
    at the team's campus, or — for an administration team only — the holder of
    an institution-wide role. They are the deliberate exception to "one employee
    sits on one chain per team": a team building a second chain reuses its
    registrar or bursar, it does not move them off the first chain.

    Two exclusions keep that exception honest:

    * a **campus-wide** holding reaches only the academic teams at its own
      campus, so a team elsewhere — or an administration team — never sees it;
    * an **institution-wide** holding is an administration office, so an
      academic team does not see it at all;
    * the team's **designated manager** is not in this set. A manager joins
      their own team's roster to route their own leave, and once there they are
      an ordinary member of one of its chains rather than a wide holder who can
      sit on all of them.
    """
    if team is None:
        return set()
    ids: set[int] = set()
    if team.category == Team.Category.ADMINISTRATION:
        ids.update(
            RoleAssignment.objects.filter(
                role__is_institution_wide=True, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    ids.update(
        TeamRoleAssignment.objects.filter(
            team=team, user__is_active=True, is_team_manager=False
        ).values_list("user_id", flat=True)
    )
    if team.category == Team.Category.ACADEMIC and team.campus_id is not None:
        ids.update(
            CampusRoleAssignment.objects.filter(
                campus_id=team.campus_id, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    return ids


def _employee_profile_for(user: User):
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        profile = EmployeeProfile.objects.filter(user=user).select_related("user").first()
    return profile


def add_team_member(*, team: Team, user: User, actor) -> EmployeeProfile:
    """Place an active employee on a team as a normal member.

    Team membership is the eligibility pool for workflow membership and for
    approver eligibility: the employee's :attr:`EmployeeProfile.team` is the
    single record of which team's approval chain their leave routes through.

    Membership is scoped two ways. The team's **category** decides who may
    belong: an academic team takes academic employees, an administration team
    takes administration employees, and a mismatch is refused rather than
    allowed to sit on the roster until routing surprises someone. And a **wide
    approver** — institution-wide, team-wide on this team, or campus-wide at
    this team's campus — is not a normal member: they staff steps from the
    Approvers tab and are kept out of the roster, so being an approver never
    also quietly routes someone's leave as a member.

    The team's **designated manager** is the one exception. Their own leave
    must route through the team they run, and only a roster row makes that
    true, so the manager may place themselves here. Once placed they leave
    every other team's candidate list, which is the "one team per employee"
    rule doing its job rather than a special case.

    Somebody already on a different team is refused rather than moved. Moving
    an employee off another team would leave that team with steps whose
    approvers are no longer members, and it would re-route their leave without
    HR choosing to — a deliberate edit, not a side effect of filling a roster.
    """
    if not user.is_active:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not an active user. Activate the "
            "account before adding them to a team.",
        )
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record, so there is "
            "nothing to place on a team. Complete their employee record first.",
        )
    if profile.category != team.category:
        raise WorkflowMemberError(
            "user",
            f'{_member_display_name(user)} is an '
            f'{profile.get_category_display()} employee, but "{team.name}" is an '
            f'{team.get_category_display()} team. An '
            f'{team.get_category_display()} team takes only '
            f'{team.get_category_display()} employees.',
        )
    if user.pk in wide_approver_ids_for_team(team):
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is a wide approver for this team, so "
            "they serve its steps from the Approvers tab rather than as a normal "
            "member. Remove the holding first if they should sit on the roster.",
        )
    with transaction.atomic():
        locked_profile = EmployeeProfile.objects.select_for_update().get(pk=profile.pk)
        if locked_profile.team_id == team.pk:
            return locked_profile
        if locked_profile.team_id is not None:
            current_name = (
                Team.objects.filter(pk=locked_profile.team_id)
                .values_list("name", flat=True)
                .first()
                or "another team"
            )
            raise WorkflowMemberError(
                "user",
                f'{_member_display_name(user)} is already on "{current_name}". '
                f'Remove them from that team first, or leave them on '
                f'"{current_name}" — one employee belongs to one team.',
            )
        before_team_id = locked_profile.team_id
        locked_profile.team = team
        locked_profile.save(update_fields=["team"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=locked_profile.user_id,
            target_summary=_member_display_name(locked_profile.user),
            detail=changed_fields(
                {"team_id": before_team_id},
                {"team_id": team.pk, "team": team.name},
            ),
            reason=f"Added to the {team.name} team as a normal member.",
        )
    return locked_profile


def add_team_members(
    *, team: Team, users: list[User], actor
) -> list[EmployeeProfile]:
    """Place several employees on a team in one all-or-nothing write.

    The roster picker lets HR select more than one person at once, so this
    repeats :func:`add_team_member` inside one transaction: every refusal is
    collected, and if any person cannot join, the whole selection is rolled
    back. Without the outer transaction a selection could leave half its people
    on the team and report only the one that failed, which reads as a partial
    roster nobody chose.

    A single request still reports one field error, ``users``, naming each
    person who could not join. The audit rows the successful adds wrote are
    rolled back with them.
    """
    seen: set[int] = set()
    for user in users:
        if user.pk in seen:
            raise WorkflowMemberError(
                "users",
                "Remove duplicate employees from the selection.",
            )
        seen.add(user.pk)

    if not users:
        raise WorkflowMemberError(
            "users",
            "Select at least one employee to add.",
        )

    with transaction.atomic():
        profiles: list[EmployeeProfile] = []
        refusals: list[str] = []
        for user in users:
            try:
                profiles.append(add_team_member(team=team, user=user, actor=actor))
            except WorkflowMemberError as exc:
                refusals.append(exc.message)
        if refusals:
            raise WorkflowMemberError("users", " ".join(refusals))
    return profiles


