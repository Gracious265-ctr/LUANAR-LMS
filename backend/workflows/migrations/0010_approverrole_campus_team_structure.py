"""Approver roles, campuses, teams, and the staging columns for the stage swap.

This is step 1 of 3 for making approver roles data instead of a hardcoded code
list. It only changes *shape*: the new tables appear, and the two columns that
will carry role data appear as nullable staging columns. Nothing is backfilled
here, so the migration is safe to run against a live database with applications
in flight.

The split across three migrations is deliberate and not cosmetic. Django
migrations are linear per app, and swapping a ``CharField`` that holds role
codes for a ``ForeignKey`` in a single step would require either a table rebuild
or an intermediate state Django's autodetector cannot express. So:

* **0010** (this file) — new tables + staging columns, all nullable.
* **0011** — the one handwritten data migration that creates the roles and
  copies codes into the staging columns.
* **0012** — drops the old text columns and tightens the new ones to NOT NULL.

Keeping the data step alone in the middle is what makes the sequence
reviewable: one file holds every row-level decision, and it is the only file
that needs to be read carefully.
"""


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0009_delegation_one_open_request_per_approver"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApproverRole",
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
                (
                    "code",
                    models.SlugField(
                        help_text=(
                            "Stable identifier. Immutable once any stage or "
                            "member references it."
                        ),
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Human-readable name shown wherever the role appears.",
                        max_length=80,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="What this role is responsible for.",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "history_scope",
                    models.CharField(
                        choices=[
                            ("all", "Full history"),
                            ("same_department", "Same department only"),
                            ("same_faculty", "Same faculty only"),
                            (
                                "current_financial_year",
                                "Current financial year only",
                            ),
                            ("none", "No history"),
                        ],
                        default="current_financial_year",
                        help_text="Which leave history an approver in this role may see.",
                        max_length=32,
                    ),
                ),
                (
                    "handles_cancellation",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Whether this role's stages decide Unit 18 cancellation "
                            "requests."
                        ),
                    ),
                ),
                (
                    "is_institution_wide",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Whether the role may be resolved from a global role "
                            "assignment when a team has no member holding it."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["label"]},
        ),
        migrations.CreateModel(
            name="Campus",
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
                ("code", models.SlugField(max_length=50, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="RoleAssignment",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="role_assignments",
                        to="workflows.approverrole",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="role_assignments",
                        to="users.user",
                    ),
                ),
            ],
            options={"ordering": ["role", "user"]},
        ),
        migrations.CreateModel(
            name="Team",
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
                ("code", models.SlugField(max_length=50, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The campus this team belongs to; blank when the team "
                            "is not campus-based. Informational — routing always "
                            "follows the team."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teams",
                        to="workflows.campus",
                    ),
                ),
                (
                    "workflow",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The approval workflow this team's members are routed "
                            "through. Blank means the team cannot route any "
                            "application yet."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teams",
                        to="workflows.workflow",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="TeamMember",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="team_memberships",
                        to="workflows.approverrole",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        help_text=(
                            "The team this role is held in. Note the reverse name: "
                            "the employees who belong to a team are Team.members, "
                            "while the roles they hold inside it are "
                            "Team.memberships."
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="workflows.team",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="team_memberships",
                        to="users.user",
                    ),
                ),
            ],
            options={"ordering": ["team", "role"]},
        ),
        migrations.AddConstraint(
            model_name="roleassignment",
            constraint=models.UniqueConstraint(
                fields=("user", "role"), name="roleassignment_user_role_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="teammember",
            constraint=models.UniqueConstraint(
                fields=("team", "role"), name="teammember_team_role_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="teammember",
            constraint=models.UniqueConstraint(
                fields=("team", "user"), name="teammember_team_user_unique"
            ),
        ),
        # --- staging columns -------------------------------------------------
        # ``WorkflowStage.approver_role`` is currently a varchar named
        # ``approver_role``. The final field is a FK, whose column Django names
        # ``approver_role_id`` — a different name, so the two can coexist while
        # the data is copied across in 0011. The staging field is deliberately
        # *not* a FK: making it one would install a real foreign key constraint
        # on a column that is still all NULLs, and 0012 would then have to drop
        # and re-add the constraint around the data copy.
        migrations.AddField(
            model_name="workflowstage",
            name="approver_role_ref_staging",
            field=models.BigIntegerField(
                db_column="approver_role_id",
                default=None,
                null=True,
                help_text=(
                    "Staging column: the id of the ApproverRole this stage's role "
                    "code refers to. Replaced by the real FK in 0012."
                ),
            ),
        ),
        migrations.AddField(
            model_name="applicationstage",
            name="role_ref",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The live role this stage was materialised from. Null only for "
                    "rows written before roles became data; ``role`` stays "
                    "authoritative in that case. Kept for traceability — not for "
                    "reading behaviour."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="application_stages",
                to="workflows.approverrole",
            ),
        ),
        migrations.AddField(
            model_name="applicationstage",
            name="history_scope",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Snapshot of the role's leave-history scope at materialization. "
                    "This — not the live role — is what an in-flight application is "
                    "judged by, so widening or narrowing a role later never "
                    "rewrites the review history of an application already in "
                    "flight. Blank on rows written before roles became data."
                ),
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="applicationstage",
            name="handles_cancellation",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Snapshot of the role's cancellation-handling flag at "
                    "materialization, so an in-flight application never changes "
                    "behaviour when HR edits the role."
                ),
            ),
        ),
    ]
