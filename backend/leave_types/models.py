"""Leave type registry — the one place every leave rule lives.

``leave_config`` owns ``LeaveType`` (refinement unit 06): the app that lets HR
*create* a leave type also owns its data, the same way ``org`` owns
``OrgUnit``.  Every other module FKs into this model and reads its rule fields
through :mod:`leave_config.services` — never duplicating a rule of its own.

Two migrations moved that responsibility here:

* ``leave_config.0001`` took ownership of the pre-existing ``leave_leavetype``
  table (state-only, no DDL) — the ``leave`` app's copy of the model was then
  dropped state-only, so real data never moved.
* ``leave_config.0002`` folded the old effective-dated ``leave.LeaveRule`` rows
  into the type itself, retiring that model (and the Leave Rules screens) so
  there is exactly one number per rule per type.

The table name and the integer primary key are deliberately left as they were;
converting them would have rewritten every referencing row for no gain.
"""

from django.db import models
from django.utils.text import slugify


class BranchScope(models.TextChoices):
    """Which arm of the institution a leave type applies to."""

    ACADEMIC = "academic", "Academic"
    ADMINISTRATIVE = "administrative", "Administrative"
    BOTH = "both", "Both"


class GenderEligibility(models.TextChoices):
    """Gender dimension of eligibility; unset/Any means no restriction."""

    ANY = "any", "Any"
    MALE = "male", "Male"
    FEMALE = "female", "Female"


#: Restricted palette (§3.3): status-safe tokens only, so a chosen colour can
#: never clash with the badge/status colours used everywhere else in the UI.
ALLOWED_COLOR_CHOICES = [
    ("blue", "Blue"),
    ("green", "Green"),
    ("red", "Red"),
    ("orange", "Orange"),
    ("yellow", "Yellow"),
    ("purple", "Purple"),
    ("gray", "Gray"),
    ("indigo", "Indigo"),
]


class LeaveType(models.Model):
    """One named leave type and every rule attached to it.

    There is deliberately **no** entitlement field here (§1.3): how many days of
    this type an employee gets is grade-based and lives in
    ``leave.GradeLeaveEntitlement``.  A rule edit is forward-looking only —
    submitted applications keep the ``rules_snapshot`` they were filed with.
    """

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True, blank=True)

    # ── Basics ────────────────────────────────────────────────────────────
    color = models.CharField(
        max_length=20,
        choices=ALLOWED_COLOR_CHOICES,
        default="blue",
        help_text="Swatch shown against this type in employee-facing lists.",
    )
    description = models.TextField(
        blank=True,
        help_text="Shown to employees as help text when they pick this type.",
    )

    # ── Eligibility (§1.4 — three independently optional dimensions) ──────
    branch_scope = models.CharField(
        max_length=15,
        choices=BranchScope.choices,
        default=BranchScope.BOTH,
        help_text="'Both' places no restriction on the staff branch.",
    )
    eligible_grades = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Grade identifiers this type is limited to (external ids from the "
            "organisation provider, as used by GradeLeaveEntitlement). "
            "An empty list means every grade is eligible."
        ),
    )
    eligible_gender = models.CharField(
        max_length=10,
        choices=GenderEligibility.choices,
        default=GenderEligibility.ANY,
        help_text="'Any' places no restriction on gender.",
    )

    # ── Rules ─────────────────────────────────────────────────────────────
    requires_supporting_document = models.BooleanField(default=False)
    max_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Longest single application in days; blank means no maximum.",
    )
    notice_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Days of advance notice this type requires (Unit 14 submission "
            "validation) and therefore how far ahead the Leave Plans reminder "
            "fires. Null means no minimum and no reminder window."
        ),
    )

    # ── The Unit 14 validation engine's machine-readable rule set ─────────
    eligibility = models.TextField(
        blank=True,
        help_text=(
            "Human-readable eligibility description shown to approvers; the "
            "validation engine reads ``eligibility_rules`` below."
        ),
    )
    eligibility_rules = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Machine-readable eligibility rules for the validation engine, each "
            "``{'type': ..., 'params': {...}}``. Rule types: ``gender``, "
            "``min_service``, ``grade_range``, ``employee_category``. Unknown "
            "rule types fail closed."
        ),
    )
    consumes_annual_entitlement = models.BooleanField(
        default=False,
        help_text=(
            "Whether applying for this type draws down the employee's annual "
            "leave balance."
        ),
    )

    # ── Planning / approval ───────────────────────────────────────────────
    plannable = models.BooleanField(
        default=True,
        help_text=(
            "Whether employees may pre-plan this type (Leave Plans). Types that "
            "are rarely planned ahead — sick leave, for instance — set this off "
            "so they never appear on the Create a Plan form."
        ),
    )
    requires_institutional_registrar_approval = models.BooleanField(
        default=False,
        help_text=(
            "Escalate approvals on this type to the Institutional Registrar. "
            "Read by the approvals chain resolver; academic chains never reach "
            "the registrar regardless of this flag."
        ),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Whether HR still offers this type. Deactivating hides it from new "
            "applications and plans without deleting it, so applications "
            "already filed against it keep their type and its rules keep their "
            "history. Never hard-delete a referenced type (§1.5)."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        # The pre-existing table, kept by the state-only move (§1.1): renaming
        # it would rewrite the constraints every referencing table hangs off.
        db_table = "leave_leavetype"

    def __str__(self) -> str:
        return self.name

    @property
    def eligible_grade_ids(self) -> list[str]:
        """Normalised copy of :attr:`eligible_grades` (upper-cased, no blanks)."""
        return [
            str(value).strip().upper()
            for value in (self.eligible_grades or [])
            if str(value).strip()
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        if not self.code:
            self.code = slugify(self.name)
        else:
            self.code = self.code.strip().lower()
        super().save(*args, **kwargs)
