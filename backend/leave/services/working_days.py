"""Working-day counting for the paths outside the validation pipeline.

The pipeline (``leave/validation``) counts days itself while validating a
submission. Drafts and the ``preview-days`` endpoint need the same number
*before* submission, and this module is their only entry point, so there is
exactly one counting rule in the product: weekends (Saturday and Sunday) **and
configured public holidays** are not working days.

Holidays are read through the configured ``LEAVE_RULES_PROVIDER`` rather than
queried directly, so the same provider seam the pipeline uses applies here
(a test can install a stub, and a future non-database source needs no change).
"""

from datetime import date


def holidays_in_range(
    start: date, end: date, provider=None
) -> dict[date, str]:
    """Public holidays in the inclusive range ``[start, end]`` as ``{date: name}``."""
    if end < start:
        return {}
    if provider is None:
        # Imported here: ``leave.providers.database`` imports ``leave.services``,
        # so a module-level import would be circular.
        from leave.providers import get_provider

        provider = get_provider()
    return provider.get_public_holidays(start, end)


def calculate_working_days(
    start_date: date,
    end_date: date,
    *,
    holidays: set[date] | None = None,
    provider=None,
) -> int:
    """Count working days in the inclusive range ``[start_date, end_date]``.

    Returns 0 for a missing or reversed range. A day counts when it is neither a
    weekend nor a configured public holiday, so a holiday that falls on a weekend
    is still excluded and never double-counted.
    """
    if start_date is None or end_date is None or end_date < start_date:
        return 0
    if holidays is None:
        holidays = set(holidays_in_range(start_date, end_date, provider))
    from leave.validation.working_days import count_working_days

    return count_working_days(start_date, end_date, holidays)
