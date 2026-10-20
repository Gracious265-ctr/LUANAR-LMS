"""Carry rejected-leave days across a financial-year boundary.

HR runs this once when a year rolls over. It scans the *closing* year for
applications still in ``rejected`` status, computes each employee's carry-over
(see ``leave.services.carry_over``) and writes one ``LeaveCarryOver`` row per
employee naming the *opening* year as the recipient. Ordinary unused entitlement
is not carried — only days a rejection left unused.

Idempotent: a re-run for the same pair of years writes no duplicate row and
changes nothing. ``--dry-run`` reports what would be granted without writing.

By default the command rolls the currently ``active`` year into the next
configured year (the one whose ``start_date`` immediately follows the active
year's ``end_date``). Pass ``--from LABEL`` and/or ``--to LABEL`` to override.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from leave.models import FinancialYear
from leave.services import financial_year_label
from leave.services.carry_over import (
    carry_over_financial_year,
    next_financial_year,
)


class Command(BaseCommand):
    help = (
        "Carry rejected-leave days from a closing financial year into the next "
        "one. Idempotent; use --dry-run to preview."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from",
            dest="from_label",
            default=None,
            help="Closing financial-year label (e.g. 2026-27). Defaults to the active year.",
        )
        parser.add_argument(
            "--to",
            dest="to_label",
            default=None,
            help="Opening financial-year label. Defaults to the year starting right after --from.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Report what would be granted without writing any rows.",
        )

    def _resolve_year(self, label: str) -> FinancialYear:
        for year in FinancialYear.objects.all():
            if financial_year_label(year) == label:
                return year
        raise CommandError(f"No financial year matches the label {label!r}.")

    def _default_opening_year(self, closing: FinancialYear) -> FinancialYear:
        opening = next_financial_year(closing)
        if opening is None:
            raise CommandError(
                "Could not find the financial year following "
                f"{financial_year_label(closing)}; pass --to explicitly."
            )
        return opening

    def handle(self, *args, **options):
        from_label = options.get("from_label")
        to_label = options.get("to_label")
        dry_run = options.get("dry_run", False)

        if from_label:
            closing_year = self._resolve_year(from_label)
        else:
            closing_year = (
                FinancialYear.objects.filter(is_active=True)
                .order_by("-start_date")
                .first()
            )
            if closing_year is None:
                raise CommandError(
                    "No active financial year; pass --from explicitly."
                )

        if to_label:
            opening_year = self._resolve_year(to_label)
        else:
            opening_year = self._default_opening_year(closing_year)

        if financial_year_label(closing_year) == financial_year_label(opening_year):
            raise CommandError("The closing and opening years must differ.")

        results = carry_over_financial_year(
            closing_year, opening_year, dry_run=dry_run
        )

        prefix = "Would carry" if dry_run else "Carried"
        if not results:
            self.stdout.write(
                f"{prefix} no days from "
                f"{financial_year_label(closing_year)} to "
                f"{financial_year_label(opening_year)}."
            )
            return

        for row in results:
            state = "" if dry_run else (" (new)" if row["created"] else " (existing)")
            self.stdout.write(
                f"{prefix} {row['days']} days for employee "
                f"{row['employee_id']}{state}."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} days for {len(results)} employee(s) from "
                f"{financial_year_label(closing_year)} to "
                f"{financial_year_label(opening_year)}."
            )
        )
