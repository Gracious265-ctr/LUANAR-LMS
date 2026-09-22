"""Tests for reference-number generation (``leave.services.references``)."""

from django.db import transaction
from django.test import TestCase

from leave.models import ReferenceSequence
from leave.services.references import next_reference


class NextReferenceTests(TestCase):
    def test_first_reference_for_a_year(self):
        with transaction.atomic():
            self.assertEqual(next_reference("2026-27"), "LV-2026-27-000001")

    def test_sequences_increment(self):
        with transaction.atomic():
            first = next_reference("2026-27")
            second = next_reference("2026-27")
            third = next_reference("2026-27")
        self.assertEqual([first, second, third], [
            "LV-2026-27-000001",
            "LV-2026-27-000002",
            "LV-2026-27-000003",
        ])

    def test_reference_format_is_padded_to_six_digits(self):
        with transaction.atomic():
            for _ in range(13):
                next_reference("2026-27")
        seq = ReferenceSequence.objects.get(financial_year_label="2026-27")
        self.assertEqual(seq.last_value, 13)
        self.assertTrue(seq and seq.last_value)

    def test_financial_years_are_independent(self):
        with transaction.atomic():
            a1 = next_reference("2026-27")
            b1 = next_reference("2027-28")
            a2 = next_reference("2026-27")
        self.assertEqual(a1, "LV-2026-27-000001")
        self.assertEqual(a2, "LV-2026-27-000002")
        self.assertEqual(b1, "LV-2027-28-000001")

    def test_sequence_resumes_persisted_value(self):
        with transaction.atomic():
            next_reference("2026-27")  # 1
            next_reference("2026-27")  # 2
        with transaction.atomic():
            self.assertEqual(
                next_reference("2026-27"), "LV-2026-27-000003"
            )