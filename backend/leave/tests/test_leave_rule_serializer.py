"""Tests for the LeaveRuleSerializer eligibility_rules field (Unit 20)."""

from datetime import date

from django.test import TestCase

from leave.models import LeaveType
from leave.serializers import LeaveRuleSerializer


class LeaveRuleSerializerEligibilityTests(TestCase):
    def setUp(self):
        self.leave_type = LeaveType.objects.create(name="Annual Leave", code="annual")

    def valid_payload(self, eligibility_rules):
        return {
            "leave_type": self.leave_type.pk,
            "max_duration_days": 30,
            "min_notice_days": 0,
            "eligibility": "",
            "eligibility_rules": eligibility_rules,
            "requires_supporting_document": False,
            "consumes_annual_entitlement": False,
            "effective_from": date(2026, 1, 1),
        }

    def test_accepts_known_rule_types(self):
        payload = self.valid_payload(
            [
                {"type": "gender", "params": {"allowed": ["F"]}},
                {"type": "min_service", "params": {"months": 12}},
                {"type": "grade_range", "params": {"min": "A", "max": "C"}},
                {"type": "employee_category", "params": {"allowed": ["academic"]}},
            ]
        )
        serializer = LeaveRuleSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_blank_defaults_to_empty_list(self):
        payload = self.valid_payload([])
        serializer = LeaveRuleSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_unknown_rule_type(self):
        serializer = LeaveRuleSerializer(
            data=self.valid_payload([{"type": "custom", "params": {}}])
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("eligibility_rules", serializer.errors)

    def test_rejects_invalid_params(self):
        cases = [
            {"type": "gender", "params": {"allowed": ["X"]}},
            {"type": "min_service", "params": {"months": 0}},
            {"type": "grade_range", "params": {"min": "D", "max": "A"}},
            {"type": "employee_category", "params": {"allowed": ["executive"]}},
        ]
        for rule in cases:
            serializer = LeaveRuleSerializer(data=self.valid_payload([rule]))
            self.assertFalse(serializer.is_valid(), rule)
            self.assertIn("eligibility_rules", serializer.errors)