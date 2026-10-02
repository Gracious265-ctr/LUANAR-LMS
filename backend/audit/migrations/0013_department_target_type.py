"""Add ``department`` to the audit target types.

Creating a department is a configuration change HR makes, so it belongs in the
audit trail beside the teams and roles it scopes. ``AuditEntry`` is append-only
and its ``target_type`` is free text at read time, so widening the choice set
rewrites no history: an existing entry keeps the code it was written with.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0012_alter_auditentry_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditentry",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("record", "Record"),
                    ("entitlement", "Entitlement"),
                    ("leavetype", "Leave type"),
                    ("leaverule", "Leave rule"),
                    ("financialyear", "Financial year"),
                    ("publicholiday", "Public holiday"),
                    ("workflow", "Workflow"),
                    ("approver-role", "Approver role"),
                    ("campus", "Campus"),
                    ("department", "Department"),
                    ("team", "Team"),
                    ("employee", "Employee"),
                    ("application", "Application"),
                    ("delegation", "Delegation"),
                    ("reassignment", "Reassignment"),
                    ("document-template", "Document template"),
                    ("cancellation", "Cancellation request"),
                    ("balance_transaction", "Leave balance transaction"),
                ],
                help_text=(
                    "The type of record changed, e.g. entitlement or application."
                ),
                max_length=32,
            ),
        ),
    ]
