"""Compare every model against the live schema and report drift.

``manage.py makemigrations --check`` compares the model against the migration
*state* — never against the database — so a migration edited after it had
already been applied leaves the physical schema behind with nothing to notice.
``plans.0003_assigned_approver_nullable`` repairs one such case: the column
``plans_planapprovalstage.assigned_approver_id`` was created ``NOT NULL``,
the migration file was later changed to ``null=True``, and Django never
re-runs a migration it has recorded as applied. Submission 500'd on the
resulting ``IntegrityError``.

Run this against a persistent database (development or production). Against a
database that was just built from the migrations it is always clean, which is
exactly why this is a command and not a test.

Exits 1 when drift is found, 0 when the schema agrees with the models.
"""

import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Report live-schema drift between the models and information_schema."

    def handle(self, *args, **options):
        findings = self.collect()
        if not findings:
            self.stdout.write(self.style.SUCCESS("No schema drift detected."))
            return

        self.stdout.write(
            self.style.ERROR(f"{len(findings)} schema mismatch(es):")
        )
        for finding in findings:
            self.stdout.write(f"  {finding}")
        sys.exit(1)

    def collect(self) -> list[str]:
        """Every place the models and the physical schema disagree."""
        findings: list[str] = []
        for model in apps.get_models():
            if model._meta.proxy:
                continue
            findings.extend(self._check_model(model))
        return sorted(findings)

    def _check_model(self, model) -> list[str]:
        table = model._meta.db_table
        live = self._live_columns(table)
        if not live:
            return [f"{table}: the model's table is missing from the database"]

        findings: list[str] = []
        expected: dict[str, bool] = {}
        for field in model._meta.local_fields:
            column = field.column
            expected[column] = field.null
            if column not in live:
                findings.append(
                    f"{table}.{column}: declared by the model but absent "
                    f"from the database"
                )
            elif (live[column] == "YES") != field.null:
                findings.append(
                    f"{table}.{column}: model null={field.null} but the "
                    f"database has is_nullable={live[column]}"
                )

        for column in sorted(set(live) - set(expected)):
            findings.append(
                f"{table}.{column}: present in the database but not in the model"
            )
        return findings

    def _live_columns(self, table: str) -> dict[str, str]:
        """``{column: is_nullable}`` for a table, or ``{}`` when it is absent."""
        sql = (
            "SELECT column_name, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = %s"
        )
        params: list[str] = [table]
        schema = getattr(connection, "schema_name", None)
        if schema:
            sql += " AND table_schema = %s"
            params.append(schema)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return {row[0]: row[1] for row in cursor.fetchall()}
