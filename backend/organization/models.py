"""The organizational tree and the actancy that temporarily covers its approvers.

This app is an **authority**, not a workflow feature. It answers two questions
that ``workflows`` used to answer by hand:

* where does an employee sit, so a chain can be derived from the shape of the
  institution instead of from a list someone ordered by hand;
* who is covering an absent approver right now.

Nothing here routes an application. :mod:`workflows.providers` owns that, and
the tree is consumed through a provider so a team may keep its hand-configured
chain until HR has bound it to a unit. That split is deliberate: the tree is the
new authority, ``Workflow``/``Section`` is the legacy one, and they are allowed
to disagree for as long as the migration takes.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from organization.exceptions import OrgUnitCycleError


class OrgUnit(models.Model):
    """One node in the institutional tree.

    An approval chain is the path from an employee's **home unit** up to the
    root, taking the designated approver at each level on the way. Storing that
    path per team (as a hand-ordered ``Section`` list does) means the same four
    rows get re-entered once per team and go stale the moment somebody is
    promoted. Deriving it from the tree makes promotion a single edit that
    applies everywhere at once.

    Each unit names **one** designated approver and **one** role that approver is
    expected to hold. They are deliberately separate: the role is what the
    approval history records and what the stage is labelled, while the person is
    who actually gets the notification today. When the two disagree — an
    acting approver, or a promotion that has not been written up yet — the
    resolver prefers the designated approver and records the role it *should*
    have been, so the history never claims somebody approved in a capacity they
    did not hold.

    Cycle safety, the root uniqueness rule, and the parent-type matrix live in
    :meth:`clean`. None of them can be expressed as a SQL constraint on
    PostgreSQL without a recursive CTE or a trigger, and getting them wrong
    means an approval chain that silently loops or stops at a non-existent
    ancestor. They are enforced here and re-checked in the write services.
    """

    class UnitType(models.TextChoices):
        """The kinds of node the tree is allowed to contain.

        ``ADMIN_DEPARTMENT`` is split out from ``DEPARTMENT`` because the
        academic branch and the administrative branch escalate differently: a
        Head of Department escalates through their faculty, while a head of an
        administrative department escalates straight to the institution.
        """

        INSTITUTION = "institution", "Institution"
        FACULTY = "faculty", "Faculty"
        DEPARTMENT = "department", "Department"
        ADMIN_DEPARTMENT = "admin_department", "Administrative department"
        PROGRAMME = "programme", "Programme"
        TEAM = "team", "Team"

    #: How far a chain may climb before we call the data wrong rather than
    #: walk it. A real institution is five deep; anything past this is a cycle
    #: that ``clean()`` could not see because the rows were written by a script
    #: or a data migration that skipped validation.
    MAX_DEPTH = 12

    #: Which parent types each unit type is allowed to sit under. The root is
    #: the only node with no parent, so this doubles as the list of types that
    #: may be the apex.
    ALLOWED_PARENT_TYPES: dict[str, tuple[str, ...]] = {
        UnitType.INSTITUTION: (),
        UnitType.FACULTY: (UnitType.INSTITUTION,),
        UnitType.DEPARTMENT: (UnitType.INSTITUTION, UnitType.FACULTY),
        UnitType.ADMIN_DEPARTMENT: (UnitType.INSTITUTION, UnitType.FACULTY),
        UnitType.PROGRAMME: (
            UnitType.INSTITUTION,
            UnitType.FACULTY,
            UnitType.DEPARTMENT,
            UnitType.ADMIN_DEPARTMENT,
        ),
        UnitType.TEAM: (
            UnitType.DEPARTMENT,
            UnitType.ADMIN_DEPARTMENT,
            UnitType.PROGRAMME,
        ),
    }

    name = models.CharField(max_length=200)
    unit_type = models.CharField(max_length=32, choices=UnitType.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        help_text=(
            "The unit this one reports through. Null only for the institution "
            "itself; every other unit must sit under exactly one parent, which "
            "is what makes 'climb to the top' a well-defined operation."
        ),
    )
    approver_role = models.ForeignKey(
        "workflows.ApproverRole",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="org_units",
        help_text=(
            "The role the designated approver of this unit is expected to hold. "
            "Recorded on the approval stage as the approver's capacity, and "
            "used to check the designated approver is actually qualified."
        ),
    )
    designated_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="designated_org_units",
        help_text=(
            "The single person applications escalate to at this level. A unit "
            "without one cannot route — the resolver refuses to guess, because "
            "silently skipping an unstaffed level would approve somebody's "
            "leave without the person who is accountable for it."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=(
            "A retired unit stays in the tree so historical chains stay "
            "readable, but new applications never climb through it. Retiring "
            "is how a unit is removed; deleting it would orphan every stage "
            "that names it."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"], name="orgunit_parent_name_unique"
            ),
            models.UniqueConstraint(
                fields=["parent"],
                condition=Q(parent__isnull=True),
                name="orgunit_single_root_unique",
                # PostgreSQL treats NULLs as distinct in a unique index by
                # default, so without this a second parentless row sails
                # straight through and the tree ends up with two apexes.
                nulls_distinct=False,
            ),
            # The apex is the institution and the institution is the apex:
            # institution <=> parentless, every other type requires a parent.
            models.CheckConstraint(
                condition=(
                    Q(unit_type="institution", parent__isnull=True)
                    | Q(
                        unit_type__in=[
                            "faculty",
                            "department",
                            "admin_department",
                            "programme",
                            "team",
                        ],
                        parent__isnull=False,
                    )
                ),
                name="orgunit_root_is_institution",
            ),
        ]
        indexes = [
            models.Index(fields=["unit_type"], name="orgunit_type_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    # -- hierarchy -----------------------------------------------------------

    @property
    def is_root(self) -> bool:
        """Whether this unit is the apex, which must be the institution."""
        return self.parent_id is None

    def ancestors(self, *, include_self: bool = False):
        """Yield this unit's ancestors from nearest parent up to the root.

        Iterative rather than recursive so a cycle that somehow reached the
        database cannot hang the request; it is capped at ``MAX_DEPTH`` and the
        cycle guard below stops even that. Callers get units in escalation
        order, which is the order the resolver wants.
        """
        seen = {self.pk}
        current = self.parent
        if include_self:
            yield self
        depth = 0
        while current is not None and depth < self.MAX_DEPTH:
            if current.pk in seen:
                raise OrgUnitCycleError(
                    f'The unit "{current.name}" is its own ancestor. The tree '
                    "has a cycle and cannot be climbed."
                )
            seen.add(current.pk)
            yield current
            current = current.parent
            depth += 1

    def depth(self) -> int:
        """How many edges from this unit to the root; 0 for the root."""
        return sum(1 for _ in self.ancestors())

    def is_within(self, other: "OrgUnit") -> bool:
        """Whether ``other`` is this unit or one of its ancestors.

        Used to check that a home unit really does live under the unit that
        claims to escalate for it, rather than trusting the FK.
        """
        if other.pk is None or self.pk is None:
            return False
        return any(unit.pk == other.pk for unit in self.ancestors(include_self=True))

    def is_academic_branch(self) -> bool:
        """Whether this unit escalates through a faculty.

        An administrative department (HR, ICT, Bursary) reports to the
        institution rather than to a faculty, so a head of one must not be sent
        to an academic dean for approval. Walking up and stopping at the first
        administrative department keeps the rule in one place instead of
        duplicating it at every caller.
        """
        if self.unit_type == self.UnitType.ADMIN_DEPARTMENT:
            return False
        for ancestor in self.ancestors():
            if ancestor.unit_type == self.UnitType.ADMIN_DEPARTMENT:
                return False
        return True

    def designated_approver_holds_role(self) -> bool:
        """Whether the designated approver is qualified for this unit's role.

        Qualification is a role holding at this unit or at any ancestor, or an
        institution-wide holding. Both live on ``RoleAssignment``; that model
        is shared with the legacy team roles, which is why this is the single
        place that decides what "holds the role" means.
        """
        from workflows.models import RoleAssignment

        if self.designated_approver_id is None or self.approver_role_id is None:
            return False
        return RoleAssignment.objects.filter(
            user_id=self.designated_approver_id,
            role_id=self.approver_role_id,
        ).filter(
            Q(org_unit__isnull=True) | Q(org_unit__in=self._self_and_ancestor_ids())
        ).exists()

    def _self_and_ancestor_ids(self) -> list[int]:
        return [unit.pk for unit in self.ancestors(include_self=True)]

    # -- validation ----------------------------------------------------------

    def clean(self) -> None:
        """Enforce the tree rules SQL cannot express."""
        super().clean()
        errors: dict[str, str] = {}

        self._validate_parent_type(errors)
        self._validate_single_root(errors)
        self._validate_no_cycle(errors)
        self._validate_designated_approver(errors)

        if errors:
            raise ValidationError(errors)

    def _validate_parent_type(self, errors: dict[str, str]) -> None:
        """The apex is the only parentless unit, and parents must be legal."""
        allowed = self.ALLOWED_PARENT_TYPES.get(self.unit_type, ())
        if self.parent_id is None:
            if self.unit_type != self.UnitType.INSTITUTION:
                errors["parent"] = (
                    f'A "{self.get_unit_type_display()}" must sit under a parent. '
                    "Only the Institution stands on its own."
                )
            return
        if not allowed:
            errors["parent"] = (
                f'A "{self.get_unit_type_display()}" is the apex of the tree and '
                "cannot be placed under another unit."
            )
            return
        parent_type = self.parent.unit_type
        if parent_type not in allowed:
            readable = ", ".join(
                self.UnitType(value).label for value in allowed
            )
            errors["parent"] = (
                f'A "{self.get_unit_type_display()}" cannot sit under a '
                f'"{self.parent.get_unit_type_display()}". Allowed parents are: '
                f"{readable}."
            )

    def _validate_single_root(self, errors: dict[str, str]) -> None:
        """Only one institution, so 'climb to the top' has one answer."""
        if self.parent_id is not None:
            return
        existing = (
            OrgUnit.objects.filter(parent__isnull=True)
            .exclude(pk=self.pk)
            .values_list("pk", flat=True)
            .first()
        )
        if existing is not None:
            errors["parent"] = (
                "The tree already has an Institution at the top. An "
                "organization has exactly one apex — make this unit a child of "
                "it instead."
            )

    def _validate_no_cycle(self, errors: dict[str, str]) -> None:
        """A unit may not be its own ancestor.

        Only reachable when a parent is chosen on an existing row, since a new
        row has nothing above it yet. Walk up from the chosen parent and refuse
        if we meet this unit.
        """
        if self.parent_id is None or self.pk is None:
            return
        seen: set[int] = set()
        current = self.parent
        hops = 0
        while current is not None and hops < self.MAX_DEPTH:
            if current.pk == self.pk:
                errors["parent"] = (
                    f'"{current.name}" is already below this unit, so making it '
                    "the parent would create a loop. Choose a unit higher up the "
                    "tree."
                )
                return
            if current.pk in seen:
                errors["parent"] = (
                    f'The tree above "{current.name}" already contains a loop, so '
                    "this unit cannot be attached to it. Repair the loop first."
                )
                return
            seen.add(current.pk)
            current = current.parent
            hops += 1

    def _validate_designated_approver(self, errors: dict[str, str]) -> None:
        """The designated approver must hold the unit's role.

        Checked only when both are set: a unit under construction may have a
        role without a person, and the resolver — not this model — is what
        refuses to route a chain through an unstaffed level.
        """
        if self.designated_approver_id is None or self.approver_role_id is None:
            return
        if self.designated_approver_holds_role():
            return
        role_label = self.approver_role.label
        errors["designated_approver"] = (
            f"{self.designated_approver.get_full_name()} does not hold the "
            f'"{role_label}" role at this unit or above it. Give them that role '
            "first, or appoint somebody who already holds it."
        )


class ActingAssignment(models.Model):
    """A temporary actancy: somebody covers an absent approver for a period.

    This is a **different axis** from ``workflows.Delegation`` and the two are
    deliberately not merged:

    * ``Delegation`` is one person handing their own authority to another
      colleague. It is person-to-person, and it does not care what position
      either of them holds.
    * ``ActingAssignment`` covers a **position**. It names a unit or a role
      that has nobody available, and it puts a person in that seat for a date
      range — an HOD on study leave, a dean on sabbatical.

    Keeping them apart matters for self-approval: a delegate does not satisfy a
    self-skip (an applicant cannot approve their own application by nominating
    a friend), and neither must an actancy. If these were one model that rule
    would have to be re-derived for each of two unrelated meanings.

    Overlap is refused rather than tolerated, because two people acting in the
    same seat is indistinguishable from nobody knowing who is in charge. The
    check lives in :func:`organization.services.create_acting_assignment`, which
    re-runs it under a row lock; :meth:`clean` covers the single-writer case
    only.
    """

    org_unit = models.ForeignKey(
        "organization.OrgUnit",
        on_delete=models.PROTECT,
        related_name="acting_assignments",
        help_text="The unit whose approver seat is being filled.",
    )
    role = models.ForeignKey(
        "workflows.ApproverRole",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="acting_assignments",
        help_text=(
            "Set when the whole role is vacant at this unit (a dean on "
            "sabbatical), as opposed to naming one person."
        ),
    )
    acting_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="acting_assignments",
        help_text=(
            "The person covering the seat. They need not hold the role "
            "themselves — that is the point of an actancy."
        ),
    )
    start_date = models.DateField(
        help_text="The first day the actancy applies."
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The last day, inclusive. Blank means open-ended: it lasts until HR "
            "ends it, which is how a resignation or a suspension is covered."
        ),
    )
    reason = models.TextField(
        blank=True,
        default="",
        help_text="Why the actancy exists, e.g. 'Dean on sabbatical'.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="acting_assignments_created",
        help_text="The HR user who recorded the actancy.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "org_unit"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(role__isnull=False, acting_user__isnull=True)
                    | Q(role__isnull=True, acting_user__isnull=False)
                ),
                name="actingassignment_one_target",
            ),
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(end_date__gte=models.F("start_date"))
                ),
                name="actingassignment_end_after_start",
            ),
        ]
        indexes = [
            models.Index(
                fields=["org_unit", "start_date"], name="actingunit_start_idx"
            ),
            models.Index(
                fields=["acting_user", "start_date"],
                name="actinguser_start_idx",
            ),
        ]

    def __str__(self) -> str:
        if self.acting_user_id is not None:
            actor = self.acting_user.get_full_name()
        elif self.role_id is not None:
            actor = f"Somebody acting for the {self.role.label}"
        else:
            actor = "An unassigned actancy"
        return f"{actor} covering {self.org_unit.name}"

    @property
    def state(self) -> str:
        """``scheduled`` / ``active`` / ``ended``, evaluated against today.

        Computed rather than stored, exactly like ``Delegation.state``: a
        date-bounded record has no business carrying a status column that a
        midnight rollover would leave stale, and there is no nightly job in this
        project that could be trusted to update it.
        """
        from django.utils import timezone

        today = timezone.localdate()
        if today < self.start_date:
            return "scheduled"
        if self.end_date is not None and today > self.end_date:
            return "ended"
        return "active"

    def is_active_on(self, day) -> bool:
        """Whether this actancy covers ``day``; endpoints are inclusive."""
        if day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date

    def overlaps(self, other: "ActingAssignment") -> bool:
        """Whether two actancies for the same seat collide on any day.

        An open-ended assignment (``end_date`` null) covers every later day, so
        it collides with anything that starts after it.
        """
        if other.org_unit_id != self.org_unit_id:
            return False
        # Two unsaved rows both have ``pk is None``; treating them as the same
        # row would make every prospective overlap look like a self-comparison.
        if self.pk is not None and other.pk == self.pk:
            return False
        if (self.role_id is None) != (other.role_id is None):
            return False
        if self.role_id is not None and self.role_id != other.role_id:
            return False
        starts_before_other_ends = (
            other.end_date is None or self.start_date <= other.end_date
        )
        other_starts_before_this_ends = (
            self.end_date is None or other.start_date <= self.end_date
        )
        return starts_before_other_ends and other_starts_before_this_ends

    def clean(self) -> None:
        """Validate the window and refuse an overlap, before any row is written.

        The database cannot enforce this: "no other actancy for this seat covers
        any of these days" is a range query across rows, not a row-local
        invariant, so a check constraint has nothing to hang it on. That leaves
        this method as the first of two defences rather than the only one --
        :func:`organization.services.create_acting_assignment` re-runs the same
        comparison under a row lock to close the window between the read and the
        insert. Both use :meth:`overlaps` so the rule has exactly one
        definition.
        """
        super().clean()
        errors: dict[str, ValidationError] = {}

        if self.role_id is None and self.acting_user_id is None:
            errors["role"] = ValidationError(
                "An acting assignment needs a person or a role.",
                code="no_target",
            )
        elif self.role_id is not None and self.acting_user_id is not None:
            errors["role"] = ValidationError(
                "An acting assignment covers either a person or a role, not both.",
                code="ambiguous_target",
            )

        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = ValidationError(
                "The last day cannot fall before the first day.",
                code="end_before_start",
            )

        if self.org_unit_id and not errors:
            self._assert_no_overlap(errors)

        if errors:
            raise ValidationError(errors)

    def _assert_no_overlap(self, errors: dict[str, ValidationError]) -> None:
        """Flag the window when this actancy collides with a recorded one."""
        # A role-scoped actancy and a person-scoped actancy occupy different
        # seats, so each kind only competes with its own.
        if self.role_id is not None:
            rivals = ActingAssignment.objects.filter(
                org_unit_id=self.org_unit_id, role_id=self.role_id
            )
        else:
            rivals = ActingAssignment.objects.filter(
                org_unit_id=self.org_unit_id, role__isnull=True
            )

        for rival in rivals:
            if self.overlaps(rival):
                errors["start_date"] = ValidationError(
                    "This overlaps an actancy already covering the same seat: "
                    f"{rival}.",
                    code="overlaps_existing",
                )
                return
