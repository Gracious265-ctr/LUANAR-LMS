"""Swap role-code text columns for role foreign keys, and finish the schema.

Step 3 of 3. 0011 has already copied every code into a real role and written the
per-stage snapshots, so from here on the old text columns carry no information
the new ones do not — they can go.

The two swaps are structurally different and handled differently:

* ``ApplicationStage.role`` keeps its name and just loses its ``choices`` and
  grows to 50 characters. That is a plain ``AlterField``; the column is
  untouched and every existing row keeps its snapshot.

* ``WorkflowStage.approver_role`` becomes a ``ForeignKey``. A Django FK column
  is named ``<field>_id``, so the final column (``approver_role_id``) and the old
  text column (``approver_role``) are different columns, and 0010 already staged
  the data in the right one. The swap therefore reduces to: drop the text column,
  and tell Django the surviving column is the FK. The state half of that is a
  rename plus an ``AlterField``; the database half is a single ``DROP COLUMN``.

  The drop is a raw ``DROP COLUMN`` rather than ``RemoveField`` because the
  reverse of ``RemoveField`` re-adds the column as ``NOT NULL`` with no default,
  which fails on any table that still has rows. Handling the reverse by hand
  makes the sequence genuinely reversible: the column comes back nullable, the
  codes are written into it from the roles, and only then is it tightened.
"""

import django.db.models.deletion
from django.db import migrations, models

STAGE_TABLE = "workflows_workflowstage"
LEGACY_COLUMN = "approver_role"
FK_COLUMN = "approver_role_id"


def _drop_legacy_column(apps, schema_editor):
    """Forward: the text column has been fully copied, so drop it."""
    schema_editor.execute(
        f'ALTER TABLE {STAGE_TABLE} DROP COLUMN IF EXISTS "{LEGACY_COLUMN}"'
    )


def _restore_legacy_column(apps, schema_editor):
    """Reverse: recreate the text column and refill it from the roles.

    Nullable while it is refilled, then tightened — the table may hold rows, and
    a ``NOT NULL`` column with no default cannot be added to one.
    """
    schema_editor.execute(
        f'ALTER TABLE {STAGE_TABLE} ADD COLUMN IF NOT EXISTS "{LEGACY_COLUMN}" '
        "varchar(50) NULL"
    )
    schema_editor.execute(
        f'UPDATE {STAGE_TABLE} SET "{LEGACY_COLUMN}" = role.code '
        "FROM workflows_approverrole AS role "
        f'WHERE role.id = {STAGE_TABLE}."{FK_COLUMN}"'
    )
    schema_editor.execute(
        f'ALTER TABLE {STAGE_TABLE} ALTER COLUMN "{LEGACY_COLUMN}" SET NOT NULL'
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0011_backfill_approver_roles"),
    ]

    operations = [
        # --- ApplicationStage: keep the text, drop the choices --------------
        # ``role`` stays a plain string forever. Removing the hardcoded
        # ``choices`` is what lets a role HR creates later be snapshotted here
        # without a code change; widening to 50 matches ApproverRole.code, which
        # is a SlugField and so may be longer than the old 20.
        migrations.AlterField(
            model_name="applicationstage",
            name="role",
            field=models.CharField(
                help_text=(
                    "The approver role responsible for this stage, snapshotted as "
                    "its code. Kept as a plain string — and kept forever — so a "
                    "later rename or retirement of the role can never rewrite "
                    "history."
                ),
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="applicationstage",
            name="role_label",
            field=models.CharField(
                help_text=(
                    "Human-readable label for ``role``, snapshotted at "
                    "materialization."
                ),
                max_length=80,
            ),
        ),
        # --- WorkflowStage: text column out, FK in --------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_drop_legacy_column, _restore_legacy_column),
            ],
            state_operations=[
                # Forget the old text column. The database half of this is the
                # DROP COLUMN above; here it just stops being part of the model.
                migrations.RemoveField(
                    model_name="workflowstage",
                    name="approver_role",
                ),
                # The staging column is already named the way the FK wants it
                # (``db_column="approver_role_id"``), so this rename is a
                # bookkeeping step: it gives the column the field name the model
                # declares.
                migrations.RenameField(
                    model_name="workflowstage",
                    old_name="approver_role_ref_staging",
                    new_name="approver_role",
                ),
                migrations.AlterField(
                    model_name="workflowstage",
                    name="approver_role",
                    field=models.ForeignKey(
                        help_text="The role whose holder approves this stage.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="workflow_stages",
                        to="workflows.approverrole",
                    ),
                ),
            ],
        ),
    ]
