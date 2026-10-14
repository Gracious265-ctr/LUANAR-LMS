"""On-demand LUANAR default configuration, setup status, and year rollover.

A bare install has no approver roles (migration 0028 removes the seed), no leave
types, no entitlement bands, and no financial year. The ordered chain HR walks
to make the system usable — financial year, leave types and entitlements, roles,
then a first team — is what this module collapses: one audited, idempotent
``apply_defaults`` action plus a live ``setup_status`` read the setup hub renders.

The preset is **data, applied by HR, never a migration**. It creates what is
missing, skips what already exists (including rows HR has since edited), and
never overwrites. Re-running it is always safe, which is what lets the hub offer
it as a plain button.

Nothing here is imported at module load by the apps it touches: ``workflows`` is
imported lazily inside the functions that need it, mirroring the old (deleted)
``leave.defaults`` module, so ``leave`` stays importable without ``workflows``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import record_audit

from ..models import FinancialYear, GradeEntitlement, LeaveRule, LeaveType

#: The target id and summary of the "who applied the defaults" audit entry.
PRESET_TARGET_ID = "luanar-defaults"
PRESET_SUMMARY = "LUANAR default configuration"

#: Grade ranges and the annual entitlement each is granted. The untyped band
#: (``leave_type=None``) is the historical annual entitlement, which is what the
#: balance resolver falls back to.
ENTITLEMENT_BANDS: tuple[tuple[str, str, int], ...] = (
    ("A", "C", 21),
    ("D", "G", 24),
    ("H", "U", 30),
)

#: Built-in leave types with their first rule. No rule requires a supporting
#: document by default; HR toggles that per rule afterwards.
DEFAULT_LEAVE_RULES: tuple[dict, ...] = (
    {
        "code": "annual",
        "name": "Annual leave",
        "max_duration_days": 30,
        "consumes_annual_entitlement": True,
    },
    {
        "code": "maternity",
        "name": "Maternity leave",
        "max_duration_days": 90,
        "eligibility_rules": [{"type": "gender", "params": {"allowed": ["F"]}}],
    },
    {
        "code": "paternity",
        "name": "Paternity leave",
        "max_duration_days": 10,
        "eligibility_rules": [{"type": "gender", "params": {"allowed": ["M"]}}],
    },
    {
        "code": "compassionate",
        "name": "Compassionate leave",
        "max_duration_days": 5,
    },
)


@dataclass
class ApplyResult:
    """What an ``apply_defaults`` run created, skipped, and whether it wrote."""

    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False

    @property
    def total_created(self) -> int:
        return sum(self.created.values())

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "skipped": self.skipped,
            "total_created": self.total_created,
            "dry_run": self.dry_run,
        }


def financial_year_bounds(today: date) -> tuple[date, date]:
    """The 1 July – 30 June window around ``today``."""
    if today.month >= 7:
        return date(today.year, 7, 1), date(today.year + 1, 6, 30)
    return date(today.year - 1, 7, 1), date(today.year, 6, 30)


def _ensure_financial_year(*, actor, dry_run: bool, result: ApplyResult) -> None:
    today = timezone.localdate()
    if FinancialYear.objects.filter(
        start_date__lte=today, end_date__gte=today
    ).exists():
        result.skipped["financial_year"] = 1
        return
    result.created["financial_year"] = 1
    if dry_run:
        return
    start, end = financial_year_bounds(today)
    year = FinancialYear.objects.create(
        start_date=start,
        end_date=end,
        is_active=not FinancialYear.objects.filter(is_active=True).exists(),
    )
    record_audit(
        actor=actor,
        action=AuditEntry.Action.CREATED,
        target_type=AuditEntry.TargetType.FINANCIAL_YEAR,
        target_id=year.pk,
        target_summary=str(year),
        detail={
            "before": None,
            "after": {
                "start_date": year.start_date.isoformat(),
                "end_date": year.end_date.isoformat(),
                "is_active": year.is_active,
            },
        },
    )


def _ensure_entitlements(*, actor, dry_run: bool, result: ApplyResult) -> None:
    today = timezone.localdate()
    created = skipped = 0
    for grade_start, grade_end, days in ENTITLEMENT_BANDS:
        # The unique key is (type, range), so an existing band for the range is
        # left exactly as HR configured it — never re-dated, never re-numbered.
        if GradeEntitlement.objects.filter(
            leave_type__isnull=True, grade_start=grade_start, grade_end=grade_end
        ).exists():
            skipped += 1
            continue
        created += 1
        if dry_run:
            continue
        band = GradeEntitlement.objects.create(
            grade_start=grade_start,
            grade_end=grade_end,
            days=days,
            effective_from=today,
            leave_type=None,
        )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.ENTITLEMENT,
            target_id=band.pk,
            target_summary=str(band),
            detail={
                "before": None,
                "after": {
                    "grade_start": band.grade_start,
                    "grade_end": band.grade_end,
                    "days": band.days,
                    "effective_from": band.effective_from.isoformat(),
                },
            },
        )
    result.created["entitlements"] = created
    result.skipped["entitlements"] = skipped


def _ensure_leave_types(*, actor, dry_run: bool, result: ApplyResult) -> None:
    today = timezone.localdate()
    created_types = skipped_types = created_rules = skipped_rules = 0
    for item in DEFAULT_LEAVE_RULES:
        leave_type = LeaveType.objects.filter(code=item["code"]).first()
        if leave_type is None:
            leave_type = LeaveType.objects.filter(name__iexact=item["name"]).first()
        if leave_type is None:
            created_types += 1
            created_rules += 1
            if dry_run:
                continue
            leave_type = LeaveType.objects.create(
                name=item["name"], code=item["code"], is_active=True
            )
            record_audit(
                actor=actor,
                action=AuditEntry.Action.CREATED,
                target_type=AuditEntry.TargetType.LEAVE_TYPE,
                target_id=leave_type.pk,
                target_summary=str(leave_type),
                detail={
                    "before": None,
                    "after": {
                        "name": leave_type.name,
                        "code": leave_type.code,
                        "is_active": leave_type.is_active,
                    },
                },
            )
        else:
            skipped_types += 1
            # A type HR already has is never touched; only its missing first
            # rule is offered, and only when it has no rule at all.
            if leave_type.rules.exists():
                skipped_rules += 1
                continue
            created_rules += 1
            if dry_run:
                continue

        rule = LeaveRule.objects.create(
            leave_type=leave_type,
            max_duration_days=item["max_duration_days"],
            eligibility="",
            eligibility_rules=item.get("eligibility_rules", []),
            min_notice_days=0,
            requires_supporting_document=False,
            consumes_annual_entitlement=item.get(
                "consumes_annual_entitlement", False
            ),
            effective_from=today,
        )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.LEAVE_RULE,
            target_id=rule.pk,
            target_summary=str(rule),
            detail={
                "before": None,
                "after": {
                    "leave_type": leave_type.pk,
                    "max_duration_days": rule.max_duration_days,
                    "eligibility_rules": rule.eligibility_rules,
                    "min_notice_days": rule.min_notice_days,
                    "requires_supporting_document": (
                        rule.requires_supporting_document
                    ),
                    "consumes_annual_entitlement": (
                        rule.consumes_annual_entitlement
                    ),
                    "effective_from": rule.effective_from.isoformat(),
                },
            },
        )
    result.created["leave_types"] = created_types
    result.created["leave_rules"] = created_rules
    result.skipped["leave_types"] = skipped_types
    result.skipped["leave_rules"] = skipped_rules


def _ensure_roles(*, actor, dry_run: bool, result: ApplyResult) -> None:
    from org.models import ApproverRole
    from workflows.presets import ROLE_SPECS

    created = skipped = 0
    for code, spec in ROLE_SPECS.items():
        if ApproverRole.objects.filter(code=code).exists():
            skipped += 1
            continue
        created += 1
        if dry_run:
            continue
        role = ApproverRole.objects.create(
            code=code,
            label=spec["label"],
            description=spec["description"],
            history_scope=spec["history_scope"],
            handles_cancellation=spec["handles_cancellation"],
            is_institution_wide=spec["is_institution_wide"],
            is_active=True,
        )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail={
                "before": None,
                "after": {
                    "code": role.code,
                    "label": role.label,
                    "description": role.description,
                    "history_scope": role.history_scope,
                    "handles_cancellation": role.handles_cancellation,
                    "is_institution_wide": role.is_institution_wide,
                    "is_active": role.is_active,
                },
            },
        )
    result.created["roles"] = created
    result.skipped["roles"] = skipped


def apply_defaults(*, actor, dry_run: bool = False) -> ApplyResult:
    """Create the LUANAR defaults, skipping anything that already exists.

    Additive and idempotent: each entity is keyed on its natural key, and an
    existing row is counted as skipped and left untouched. With ``dry_run`` the
    same pass runs without writing, so the hub can preview exactly what the
    button would create.
    """
    result = ApplyResult(dry_run=dry_run)
    if dry_run:
        _ensure_financial_year(actor=actor, dry_run=True, result=result)
        _ensure_entitlements(actor=actor, dry_run=True, result=result)
        _ensure_leave_types(actor=actor, dry_run=True, result=result)
        _ensure_roles(actor=actor, dry_run=True, result=result)
        return result

    with transaction.atomic():
        _ensure_financial_year(actor=actor, dry_run=False, result=result)
        _ensure_entitlements(actor=actor, dry_run=False, result=result)
        _ensure_leave_types(actor=actor, dry_run=False, result=result)
        _ensure_roles(actor=actor, dry_run=False, result=result)
        # Only summarise a run that actually wrote something; a no-op re-run is
        # not an event worth a second entry per click.
        if result.total_created:
            record_audit(
                actor=actor,
                action=AuditEntry.Action.PRESET_APPLIED,
                target_type=AuditEntry.TargetType.RECORD,
                target_id=PRESET_TARGET_ID,
                target_summary=PRESET_SUMMARY,
                detail={
                    "summary": (
                        "Applied the LUANAR default configuration from the setup "
                        "hub."
                    ),
                    "created": result.created,
                    "skipped": result.skipped,
                },
            )
    return result


def setup_status() -> dict:
    """The setup spine's completion, derived from live data (never a flag).

    Each step reports ``done`` plus the count it is judged on, so the hub can
    show "3 leave types" beside a tick. Anything already configured is therefore
    already complete for an existing install — the hub never asks HR to redo it.
    """
    from org.models import ApproverRole, Team

    today = timezone.localdate()
    has_year = FinancialYear.objects.filter(
        start_date__lte=today, end_date__gte=today
    ).exists()
    leave_types = LeaveType.objects.count()
    entitlements = GradeEntitlement.objects.count()
    roles = ApproverRole.objects.filter(is_active=True).count()
    active_teams = Team.objects.filter(status=Team.Status.ACTIVE).count()

    steps = {
        "financial_year": {"done": has_year, "count": 1 if has_year else 0},
        "leave_types": {"done": leave_types > 0, "count": leave_types},
        "entitlements": {"done": entitlements > 0, "count": entitlements},
        "roles": {"done": roles > 0, "count": roles},
        "teams": {"done": active_teams > 0, "count": active_teams},
    }
    return {
        "steps": steps,
        "complete": all(step["done"] for step in steps.values()),
    }


def _next_financial_year_bounds() -> tuple[date, date]:
    """The year after the latest configured one (a full 1 Jul – 30 Jun)."""
    latest = FinancialYear.objects.order_by("-end_date").first()
    if latest is None:
        return financial_year_bounds(timezone.localdate())
    start = latest.end_date + timedelta(days=1)
    end = date(start.year + 1, start.month, start.day) - timedelta(days=1)
    return start, end


def rollover_financial_year(*, actor) -> ApplyResult:
    """Open the next financial year, carrying the current policy forward.

    Creates the following 1 July – 30 June period (active when no other year is)
    and re-affirms each leave type's current rule as effective from the new
    year, so the policy HR set last year is explicit in the new one. Entitlement
    bands are deliberately *not* copied: a band is a single row keyed on its
    grade range and persists across years by design, while public holidays are
    date-unique and belong to whichever year they fall in, so neither can or
    should be duplicated.

    Idempotent: a year already opened, or a type already having a rule in the
    new year, is skipped.
    """
    result = ApplyResult()
    start, end = _next_financial_year_bounds()
    today = timezone.localdate()

    # If the active year already starts in the future we have rolled ahead of
    # schedule; a repeated click must not skip another whole year forward.
    reference = (
        FinancialYear.objects.filter(is_active=True).order_by("-start_date").first()
    ) or FinancialYear.objects.order_by("-end_date").first()
    if reference is not None and reference.start_date > today:
        result.skipped["financial_year"] = 1
        return result

    with transaction.atomic():
        if FinancialYear.objects.filter(start_date=start, end_date=end).exists():
            result.skipped["financial_year"] = 1
            year = FinancialYear.objects.get(start_date=start, end_date=end)
        else:
            # Activating a year retires the previous active one, the same
            # single-active rule the financial-year endpoint and admin apply.
            FinancialYear.objects.filter(is_active=True).update(is_active=False)
            year = FinancialYear.objects.create(
                start_date=start,
                end_date=end,
                is_active=True,
            )
            result.created["financial_year"] = 1
            record_audit(
                actor=actor,
                action=AuditEntry.Action.CREATED,
                target_type=AuditEntry.TargetType.FINANCIAL_YEAR,
                target_id=year.pk,
                target_summary=str(year),
                detail={
                    "before": None,
                    "after": {
                        "start_date": year.start_date.isoformat(),
                        "end_date": year.end_date.isoformat(),
                        "is_active": year.is_active,
                    },
                },
                reason="Rolled the financial year forward from the setup hub.",
            )

        created_rules = skipped_rules = 0
        for leave_type in LeaveType.objects.filter(is_active=True):
            if leave_type.rules.filter(effective_from__gte=start).exists():
                skipped_rules += 1
                continue
            current = (
                leave_type.rules.filter(effective_from__lte=today)
                .order_by("-effective_from")
                .first()
            )
            if current is None:
                skipped_rules += 1
                continue
            rule = LeaveRule.objects.create(
                leave_type=leave_type,
                max_duration_days=current.max_duration_days,
                eligibility=current.eligibility,
                eligibility_rules=current.eligibility_rules,
                min_notice_days=current.min_notice_days,
                requires_supporting_document=current.requires_supporting_document,
                consumes_annual_entitlement=current.consumes_annual_entitlement,
                effective_from=start,
            )
            created_rules += 1
            record_audit(
                actor=actor,
                action=AuditEntry.Action.CREATED,
                target_type=AuditEntry.TargetType.LEAVE_RULE,
                target_id=rule.pk,
                target_summary=str(rule),
                detail={
                    "before": None,
                    "after": {
                        "leave_type": leave_type.pk,
                        "max_duration_days": rule.max_duration_days,
                        "effective_from": rule.effective_from.isoformat(),
                        "carried_from": current.pk,
                    },
                },
                reason="Carried into the new financial year.",
            )
        result.created["leave_rules"] = created_rules
        result.skipped["leave_rules"] = skipped_rules

        if result.total_created:
            record_audit(
                actor=actor,
                action=AuditEntry.Action.PRESET_APPLIED,
                target_type=AuditEntry.TargetType.RECORD,
                target_id=PRESET_TARGET_ID,
                target_summary=PRESET_SUMMARY,
                detail={
                    "summary": (
                        f"Rolled the financial year forward to "
                        f"{year.start_date.isoformat()}."
                    ),
                    "created": result.created,
                    "skipped": result.skipped,
                },
            )
    return result
