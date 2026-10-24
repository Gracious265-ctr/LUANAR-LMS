"""Fold every ``leave.LeaveRule`` onto the type it belongs to (§4.2).

One number per rule per type: this migration writes the new rule columns on
``leave_leavetype``, copies the effective-dated rule rows across, then drops the
old ``plan_notice_days`` column that the single ``notice_days`` replaces. The
``leave.LeaveRule`` model itself is retired by ``leave.0021`` — it is kept in
the migration state until then so this data migration can read it.

Which rule wins, when a type has several:

* the rule in force today, i.e. the greatest ``effective_from`` that is on or
  before the migration date;
* a type with only pending rules keeps the earliest of them, so it still has a
  policy once effective dating is gone;
* everything else is superseded. Carrying a *future* rule over would apply
  HR's scheduled change years early, so the fold deliberately freezes today's
  behaviour instead — no existing application's evaluation changes.

``notice_days`` is then derived rather than moved, because two numbers existed
before: ``LeaveType.plan_notice_days`` (when the Leave Plans reminder fires)
and ``LeaveRule.min_notice_days`` (the submission notice check). Unit 06
retires the split (§1.2), so:

* only a plan window → that value (a rule of 0 means "no minimum", not a
  competing value);
* only a rule minimum → that value;
* both → the larger, so neither validation nor the reminder silently loosens;
* neither → ``NULL``, meaning no minimum and no reminder window.

Reverse puts the notice window back on ``plan_notice_days`` from
``notice_days``; the rule columns simply go away with the ``AddField``s that
introduced them.
"""

import django.utils.timezone
from django.db import migrations, models
from django.db.models import F


def fold_leave_rules_into_types(apps, schema_editor):
    LeaveRule = apps.get_model("leave", "LeaveRule")
    LeaveType = apps.get_model("leave_types", "LeaveType")

    # Local import: the migration runs on a state where the model's home app
    # still owns it, and ``timezone`` is what the schema editor would use too.
    from django.utils import timezone

    today = timezone.localdate()

    rules_by_type = {}
    # ``LeaveRule.Meta.ordering`` is ``-effective_from``; order ascending here
    # so "earliest pending rule" is a plain index-0 lookup.
    for rule in LeaveRule.objects.order_by("effective_from"):
        rules_by_type.setdefault(rule.leave_type_id, []).append(rule)

    for leave_type_id, rules in rules_by_type.items():
        effective = [rule for rule in rules if rule.effective_from <= today]
        chosen = effective[-1] if effective else rules[0]

        rule_notice = chosen.min_notice_days or 0
        plan_notice = LeaveType.objects.filter(pk=leave_type_id).values_list(
            "plan_notice_days", flat=True
        ).first()
        if plan_notice is None:
            notice_days = rule_notice or None
        elif rule_notice <= 0:
            notice_days = plan_notice
        else:
            notice_days = max(plan_notice, rule_notice)

        LeaveType.objects.filter(pk=leave_type_id).update(
            max_duration_days=chosen.max_duration_days,
            notice_days=notice_days,
            requires_supporting_document=chosen.requires_supporting_document,
            consumes_annual_entitlement=chosen.consumes_annual_entitlement,
            eligibility=chosen.eligibility,
            eligibility_rules=chosen.eligibility_rules,
        )


def restore_plan_notice_days(apps, schema_editor):
    LeaveType = apps.get_model("leave_types", "LeaveType")
    LeaveType.objects.filter(notice_days__isnull=False).update(
        plan_notice_days=F("notice_days")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("leave_types", "0001_initial"),
        # ``leave.LeaveRule`` must still be in the project state: this is the
        # last migration allowed to read it.
        ("leave", "0020_gradeleaveentitlement"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavetype",
            name="branch_scope",
            field=models.CharField(
                choices=[
                    ("academic", "Academic"),
                    ("administrative", "Administrative"),
                    ("both", "Both"),
                ],
                default="both",
                help_text="'Both' places no restriction on the staff branch.",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="color",
            field=models.CharField(
                choices=[
                    ("blue", "Blue"),
                    ("green", "Green"),
                    ("red", "Red"),
                    ("orange", "Orange"),
                    ("yellow", "Yellow"),
                    ("purple", "Purple"),
                    ("gray", "Gray"),
                    ("indigo", "Indigo"),
                ],
                default="blue",
                help_text="Swatch shown against this type in employee-facing lists.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="consumes_annual_entitlement",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Whether applying for this type draws down the employee's "
                    "annual leave balance."
                ),
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="leavetype",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Shown to employees as help text when they pick this type.",
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="eligibility",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Human-readable eligibility description shown to approvers; "
                    "the validation engine reads ``eligibility_rules`` below."
                ),
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="eligibility_rules",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Machine-readable eligibility rules for the validation "
                    "engine, each ``{'type': ..., 'params': {...}}``. Rule "
                    "types: ``gender``, ``min_service``, ``grade_range``, "
                    "``employee_category``. Unknown rule types fail closed."
                ),
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="eligible_gender",
            field=models.CharField(
                choices=[("any", "Any"), ("male", "Male"), ("female", "Female")],
                default="any",
                help_text="'Any' places no restriction on gender.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="eligible_grades",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Grade identifiers this type is limited to (external ids "
                    "from the organisation provider, as used by "
                    "GradeLeaveEntitlement). An empty list means every grade "
                    "is eligible."
                ),
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="max_duration_days",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Longest single application in days; blank means no maximum."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="notice_days",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Days of advance notice this type requires (Unit 14 "
                    "submission validation) and therefore how far ahead the "
                    "Leave Plans reminder fires. Null means no minimum and no "
                    "reminder window."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="requires_institutional_registrar_approval",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Escalate approvals on this type to the Institutional "
                    "Registrar. Read by the approvals chain resolver; academic "
                    "chains never reach the registrar regardless of this flag."
                ),
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="requires_supporting_document",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(
            fold_leave_rules_into_types, restore_plan_notice_days
        ),
        migrations.RemoveField(
            model_name="leavetype",
            name="plan_notice_days",
        ),
    ]
