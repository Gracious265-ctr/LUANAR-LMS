from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from audit.serializers import AuditedModelSerializer

from ..models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
    SupportingDocument,
)
from ..services import (
    find_overlapping_financial_year,
    find_overlapping_rule,
    normalize_grade,
    normalize_leave_code,
)


class GradeEntitlementSerializer(AuditedModelSerializer):
    """HR-facing serializer for grade/entitlement rules."""

    audit_prefix = "grade_entitlement"
    audit_fields = ["grade_start", "grade_end", "days", "effective_from"]

    class Meta:
        model = GradeEntitlement
        fields = ["id", "grade_start", "grade_end", "days", "effective_from"]

    def _value(self, attrs: dict, field: str):
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    def validate(self, attrs: dict) -> dict:
        grade_start = normalize_grade(self._value(attrs, "grade_start"))
        grade_end = normalize_grade(self._value(attrs, "grade_end"))
        effective_from = self._value(attrs, "effective_from")
        days = self._value(attrs, "days")

        if grade_start is None:
            raise serializers.ValidationError(
                {"grade_start": "Grade start is required."}
            )
        if grade_end is None:
            raise serializers.ValidationError({"grade_end": "Grade end is required."})
        if effective_from is None:
            raise serializers.ValidationError(
                {"effective_from": "Effective date is required."}
            )
        if days is None or days < 1:
            raise serializers.ValidationError(
                {"days": "Days must be at least 1."}
            )
        if grade_start > grade_end:
            raise serializers.ValidationError(
                {"grade_start": "Grade start must not be after grade end."}
            )

        attrs["grade_start"] = grade_start
        attrs["grade_end"] = grade_end
        self._validate_no_overlap(grade_start, grade_end)

        return attrs

    def _validate_no_overlap(self, grade_start: str, grade_end: str) -> None:
        exclude_pk = self.instance.pk if self.instance is not None else None
        overlapping = find_overlapping_rule(
            grade_start, grade_end, exclude_pk=exclude_pk
        )
        if overlapping is not None:
            raise serializers.ValidationError(
                {
                    "grade_start": (
                        "This grade range overlaps the existing rule "
                        f"{overlapping.grade_start}–{overlapping.grade_end} "
                        f"(effective {overlapping.effective_from.isoformat()})."
                    )
                }
            )


class LeaveTypeSerializer(AuditedModelSerializer):
    """HR-facing serializer for leave types (registry entries)."""

    audit_prefix = "leave_type"
    audit_fields = ["name", "code"]

    class Meta:
        model = LeaveType
        fields = ["id", "name", "code"]

    def _value(self, attrs: dict, field: str):
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    def validate(self, attrs: dict) -> dict:
        name = self._value(attrs, "name")
        name = (name or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        provided_code = self._value(attrs, "code")
        normalized = normalize_leave_code(provided_code)
        effective_code = normalized or slugify(name)
        if not effective_code:
            raise serializers.ValidationError(
                {"name": "Name must contain letters or numbers."}
            )
        attrs["code"] = effective_code

        queryset = LeaveType.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(name=name).exists():
            raise serializers.ValidationError(
                {"name": "A leave type with this name already exists."}
            )
        if queryset.filter(code=effective_code).exists():
            raise serializers.ValidationError(
                {"code": "A leave type with this code already exists."}
            )

        return attrs


class LeaveRuleSerializer(AuditedModelSerializer):
    """HR-facing serializer for effective-dated leave rules."""

    audit_prefix = "leave_rule"
    audit_fields = [
        "leave_type_id",
        "max_duration_days",
        "min_notice_days",
        "requires_supporting_document",
        "consumes_annual_entitlement",
        "eligibility",
        "eligibility_rules",
        "effective_from",
    ]

    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveRule
        fields = [
            "id",
            "leave_type",
            "leave_type_code",
            "leave_type_name",
            "max_duration_days",
            "eligibility",
            "eligibility_rules",
            "min_notice_days",
            "requires_supporting_document",
            "consumes_annual_entitlement",
            "effective_from",
        ]

    ELIGIBILITY_RULE_TYPES = ("gender", "min_service", "grade_range", "employee_category")

    def validate_eligibility_rules(self, value: list) -> list:
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Eligibility rules must be a list."
            )
        for index, item in enumerate(value):
            self._validate_eligibility_rule(index, item)
        return value

    def _validate_eligibility_rule(self, index: int, item) -> None:
        if not isinstance(item, dict):
            raise serializers.ValidationError(
                f"eligibility_rules[{index}] must be an object."
            )
        rule_type = item.get("type")
        params = item.get("params") or {}
        if rule_type not in self.ELIGIBILITY_RULE_TYPES:
            raise serializers.ValidationError(
                f"eligibility_rules[{index}] uses unknown rule type {rule_type!r}."
            )
        if not isinstance(params, dict):
            raise serializers.ValidationError(
                f"eligibility_rules[{index}].params must be an object."
            )

        if rule_type == "gender":
            allowed = params.get("allowed") or []
            if (not isinstance(allowed, list) or not allowed
                    or any(v not in ("M", "F") for v in allowed)):
                raise serializers.ValidationError(
                    f"eligibility_rules[{index}] requires params.allowed with M/F values."
                )
        elif rule_type == "min_service":
            months = params.get("months")
            if not isinstance(months, int) or months < 1:
                raise serializers.ValidationError(
                    f"eligibility_rules[{index}] requires params.months >= 1."
                )
        elif rule_type == "grade_range":
            min_grade, max_grade = params.get("min"), params.get("max")
            if not min_grade or not max_grade or min_grade > max_grade:
                raise serializers.ValidationError(
                    f"eligibility_rules[{index}] requires params.min <= params.max."
                )
        elif rule_type == "employee_category":
            allowed = params.get("allowed") or []
            if (not isinstance(allowed, list) or not allowed
                    or any(v not in ("academic", "administration") for v in allowed)):
                raise serializers.ValidationError(
                    f"eligibility_rules[{index}] requires params.allowed with "
                    "category values."
                )

    def validate_max_duration_days(self, value: int) -> int:
        if value is None or value < 1:
            raise serializers.ValidationError(
                "Max duration must be at least 1 day."
            )
        return value

    def validate_min_notice_days(self, value: int) -> int:
        if value is None or value < 0:
            raise serializers.ValidationError(
                "Minimum notice must be 0 or more days."
            )
        return value

    def validate_effective_from(self, value):
        if value is None:
            raise serializers.ValidationError("Effective date is required.")
        return value


class FinancialYearSerializer(AuditedModelSerializer):
    """HR-facing serializer for configured financial-year periods."""

    audit_prefix = "financial_year"
    audit_fields = ["start_date", "end_date", "is_active"]

    class Meta:
        model = FinancialYear
        fields = ["id", "start_date", "end_date", "is_active"]

    def _value(self, attrs: dict, field: str):
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    def validate(self, attrs: dict) -> dict:
        start_date = self._value(attrs, "start_date")
        end_date = self._value(attrs, "end_date")

        if start_date is None:
            raise serializers.ValidationError(
                {"start_date": "Start date is required."}
            )
        if end_date is None:
            raise serializers.ValidationError({"end_date": "End date is required."})
        if start_date > end_date:
            raise serializers.ValidationError(
                {"start_date": "Start date must not be after end date."}
            )

        self._validate_no_overlap(start_date, end_date)

        return attrs

    def _validate_no_overlap(self, start_date, end_date) -> None:
        exclude_pk = self.instance.pk if self.instance is not None else None
        overlapping = find_overlapping_financial_year(
            start_date, end_date, exclude_pk=exclude_pk
        )
        if overlapping is not None:
            raise serializers.ValidationError(
                {
                    "start_date": (
                        "This period overlaps the existing financial year "
                        f"{overlapping.start_date.isoformat()} – "
                        f"{overlapping.end_date.isoformat()}."
                    )
                }
            )

    def _effective_is_active(self) -> bool:
        if "is_active" in self.validated_data:
            return self.validated_data["is_active"]
        return bool(getattr(self.instance, "is_active", False))

    def _settle_active_flag(self, instance) -> None:
        if self._effective_is_active():
            FinancialYear.objects.filter(is_active=True).exclude(pk=instance.pk).update(
                is_active=False
            )

    def create(self, validated_data: dict):
        with transaction.atomic():
            instance = super(AuditedModelSerializer, self).create(validated_data)
            self._settle_active_flag(instance)
            self._audit_after_create(instance)
        return instance

    def update(self, instance, validated_data: dict):
        before = self._audit_snapshot(instance)
        with transaction.atomic():
            instance = super(AuditedModelSerializer, self).update(
                instance, validated_data
            )
            self._settle_active_flag(instance)
            instance.refresh_from_db()
            self._audit_after_update(instance, before)
        return instance


class PublicHolidaySerializer(AuditedModelSerializer):
    """HR-facing serializer for configured public-holiday dates."""

    audit_prefix = "public_holiday"
    audit_fields = ["name", "date"]

    class Meta:
        model = PublicHoliday
        fields = ["id", "name", "date"]

    def _value(self, attrs: dict, field: str):
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    def validate(self, attrs: dict) -> dict:
        name = self._value(attrs, "name")
        name = (name or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        holiday_date = self._value(attrs, "date")
        if holiday_date is None:
            raise serializers.ValidationError({"date": "Date is required."})

        queryset = PublicHoliday.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(date=holiday_date).exists():
            raise serializers.ValidationError(
                {"date": "A public holiday on this date already exists."}
            )

        return attrs


class SupportingDocumentSerializer(serializers.ModelSerializer):
    replaced_by_name = serializers.CharField(
        source="replaced_by.file_name", read_only=True, default=None
    )

    class Meta:
        model = SupportingDocument
        fields = [
            "id",
            "file_path",
            "file_url",
            "file_name",
            "file_size",
            "content_type",
            "uploaded_at",
            "status",
            "retired_at",
            "retired_by",
            "retire_reason",
            "replaced_by",
            "replaced_by_name",
        ]
        read_only_fields = fields


class LeaveApplicationSerializer(serializers.ModelSerializer):
    documents = SupportingDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = LeaveApplication
        fields = [
            "id",
            "leave_type_id",
            "start_date",
            "end_date",
            "calculated_days",
            "working_days",
            "calendar_days",
            "financial_year_label",
            "reason",
            "status",
            "reference_number",
            "created_at",
            "updated_at",
            "submitted_at",
            "documents",
        ]
        read_only_fields = [
            "id",
            "calculated_days",
            "working_days",
            "calendar_days",
            "financial_year_label",
            "status",
            "reference_number",
            "employee",
            "created_at",
            "updated_at",
            "submitted_at",
        ]
