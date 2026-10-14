"""Drop the tables sections replaced.

Step 3 of 3, and the only irreversible one. It runs after 0014 has copied every
row out, so nothing is lost: each ``WorkflowStage`` became a ``Section`` with the
same order and role, and each ``TeamMember`` became a ``SectionMember``.

This is deliberately a plain ``DeleteModel`` rather than something cleverer. The
tables being dropped are configuration — a workflow's shape, and who was on it —
and 0014's warning output is the record of what was in them. A configuration
table is not audit history: the audit log (``AuditEntry``) keeps its own
``changed_fields`` snapshots of every section and member change made through the
API, and the *behavioural* history of an application lives on
``ApplicationStage`` (role, role label, history scope, cancellation flag) and
``ApplicationStageApprover`` (who was entitled to act), none of which are touched
here.

The reverse is intentionally not provided. Reconstructing the two tables would
mean guessing: ``WorkflowStage`` had no name, so a section's HR-chosen name has
nowhere to go, and ``TeamMember`` had a role column that a section does not,
since the role lives on the section and is shared by all of its members.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0014_backfill_sections"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="teammember",
            name="teammember_team_role_unique",
        ),
        migrations.RemoveConstraint(
            model_name="teammember",
            name="teammember_team_user_unique",
        ),
        migrations.RemoveConstraint(
            model_name="workflowstage",
            name="workflowstage_order_gte_1",
        ),
        migrations.RemoveConstraint(
            model_name="workflowstage",
            name="workflowstage_workflow_order_unique",
        ),
        migrations.RemoveField(
            model_name="teammember",
            name="role",
        ),
        migrations.RemoveField(
            model_name="teammember",
            name="team",
        ),
        migrations.RemoveField(
            model_name="teammember",
            name="user",
        ),
        migrations.RemoveField(
            model_name="workflowstage",
            name="approver_role",
        ),
        migrations.RemoveField(
            model_name="workflowstage",
            name="workflow",
        ),
        migrations.DeleteModel(
            name="TeamMember",
        ),
        migrations.DeleteModel(
            name="WorkflowStage",
        ),
    ]
