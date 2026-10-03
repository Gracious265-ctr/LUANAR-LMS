"""Introduce :class:`Department`.

A department used to be a free-text string on ``EmployeeProfile`` and
``Team``, which made "the teams in ICT" something a person had to read off a
list of teams and group by hand, and made "is this approver in the same
department as this team?" a string comparison that answered differently
depending on who had typed it. It is now a row.

This model lives in ``users`` rather than ``workflows`` on purpose. It is
employee data first — it says who somebody belongs to — and ``Team`` merely
holds one, so the reference that already exists (``EmployeeProfile``) stays
in the app that owns it. The cost of that choice is that ``workflows`` will
later have to depend on ``users`` for the team-side reference, which is the
safe direction to point a dependency: Django applies the depended-upon app
first, and ``users`` is already a dependency of nearly everything.

The conversion to a reference column happens in ``0007``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_alter_user_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200, unique=True)),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "A retired department cannot be chosen for a new team "
                            "or a new employee. It is kept so historical "
                            "applications still name a department that can be "
                            "read."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]