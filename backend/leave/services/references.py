"""Reference-number generation (Unit 14, decision D8).

Format: ``LV-{financial-year-label}-{6-digit sequence}``. The sequence is per
financial year, concurrency-safe (``select_for_update``), never reused, and
retained on resubmission. Must be called inside ``transaction.atomic()``.
"""

from django.db import DatabaseError, IntegrityError, transaction

from ..models import ReferenceSequence


def next_reference(financial_year_label: str) -> str:
    """Allocate the next reference for a financial year.

    The ``get_or_create`` first-submission race is handled by catching the
    unique-constraint ``IntegrityError`` and retrying once.
    """
    label = financial_year_label
    try:
        return _allocate(label)
    except IntegrityError:
        # Another transaction created the sequence row between our SELECT and
        # INSERT; the row's reference increments are still serialized by the
        # row lock, so a single retry is sufficient.
        return _allocate(label)


def _allocate(financial_year_label: str) -> str:
    with transaction.atomic():
        seq, _created = ReferenceSequence.objects.select_for_update().get_or_create(
            financial_year_label=financial_year_label, defaults={"last_value": 0}
        )
        seq.last_value += 1
        seq.save(update_fields=["last_value"])
        return f"LV-{financial_year_label}-{seq.last_value:06d}"