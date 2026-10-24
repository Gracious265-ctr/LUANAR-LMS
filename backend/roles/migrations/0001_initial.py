# Generated for split from organisation app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
                                help_text="Stable identifier. Immutable once any stage or member references it.",
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
                                    ("same_team", "Same team only"),
                                    ("same_campus", "Same campus only"),
                                    ("same_faculty", "Same faculty only"),
                                    ("current_financial_year", "Current financial year only"),
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
                                help_text="Whether this role's stages decide Unit 18 cancellation requests.",
                            ),
                        ),
                        (
                            "is_institution_wide",
                            models.BooleanField(
                                default=False,
                                help_text="Whether the role may be resolved from a global role assignment when a team has no member holding it.",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "workflows_approverrole",
                        "ordering": ["label"],
                    },
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
                                to="roles.approverrole",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="role_assignments",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "workflows_roleassignment",
                        "ordering": ["role", "user"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="roleassignment",
                    constraint=models.UniqueConstraint(
                        fields=("user", "role"), name="roleassignment_user_role_unique"
                    ),
                ),
            ],
        ),
    ]
