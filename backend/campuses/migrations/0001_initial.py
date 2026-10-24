# Generated for split from organisation app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("roles", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
                        ("code", models.SlugField(unique=True)),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "workflows_campus",
                        "ordering": ["name"],
                    },
                ),
                migrations.CreateModel(
                    name="CampusRoleAssignment",
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
                            "campus",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="role_assignments",
                                to="campuses.campus",
                            ),
                        ),
                        (
                            "role",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="campus_role_assignments",
                                to="roles.approverrole",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="campus_role_assignments",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "workflows_campusroleassignment",
                        "ordering": ["campus", "role"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="campusroleassignment",
                    constraint=models.UniqueConstraint(
                        fields=("campus", "role"),
                        name="campusroleassignment_campus_role_unique",
                    ),
                ),
            ],
        ),
    ]
