"""Narrow ``User.role`` to system access and rewrite the old approver values.

``User.role`` used to double as "which approver role does this person hold",
which is the thing this feature removes: a role is now held through a
``TeamMember`` or a ``RoleAssignment``, and the set of possible roles is whatever
HR has created. What remains on the user is the question "what system access
does this account have", and the answer is three values.

Every old approver value is therefore rewritten:

=============  ==================  ===============================================
Old value      New value           Why
=============  ==================  ===============================================
``employee``   ``employee``        unchanged — the default, and the majority
``hr``         ``hr``              unchanged — HR keeps full system access, and
                                   :func:`is_approver_user` is OR'd with it at
                                   the API rather than being a role holding
``supervisor`` ``approver``        *not* a system access level; an active holder
``hod``        ``approver``        of a role, which is what the role tables now
``dean``       ``approver``        record. ``0011`` already moved those roles and
``registrar``  ``approver``        their per-application snapshots into data, so
``dvc``        ``approver``        nothing is lost by flattening the user row
=============  ==================  ===============================================

Runs *after* ``workflows.0011`` on purpose: 0011 finds active registrars by their
old ``User.role`` value in order to give them the institution-wide registrar
``RoleAssignment``. Narrowing the choices first would hide them.

Flattening the value does not change who can approve. ``is_approver_user`` reads
the role tables, not this column, so an approver who loses their team membership
loses approver access even though their user row still says ``approver``.
"""

from django.db import migrations, models

# Old value -> new value. Only the old approver vocabulary is listed; the rest is
# left alone.
REMAP = {
    "supervisor": "approver",
    "hod": "approver",
    "dean": "approver",
    "registrar": "approver",
    "dvc": "approver",
}

NEW_CHOICES = [
    ("employee", "Employee"),
    ("approver", "Approver"),
    ("hr", "Human Resources"),
]


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    for old, new in REMAP.items():
        User.objects.filter(role=old).update(role=new)


def backwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    # Every former approver becomes a plain employee. Which of the five roles a
    # given person held is not recorded anywhere in the user row, and the role
    # tables are about to be dropped by the reverse of 0012, so there is nothing
    # truthful to restore. ``0011``'s reverse recreates the roles, and the dev
    # seed re-establishes memberships on the next seed run.
    User.objects.filter(role="approver").update(role="employee")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_employeeprofile_team"),
        ("roles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=NEW_CHOICES,
                default="employee",
                max_length=20,
            ),
        ),
    ]
