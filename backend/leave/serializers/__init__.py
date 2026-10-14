from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

<<<<<<< HEAD
from audit.serializers import AuditedModelSerializer
=======
from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from audit.services import current_actor, record_audit
>>>>>>> feature/plans-teams

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
    ANNUAL_LEAVE_CODES,
    find_overlapping_financial_year,
    find_overlapping_rule,
    is_annual_leave_identity,
    is_annual_leave_type,
    normalize_grade,
    normalize_leave_code,
    provision_annual_leave,
    resolve_leave_rule,
    find_annual_leave_type,
    resolve_grade_entitlement,
)
from ..services.storage import safe_signed_document_url


class GradeEntitlementSerializer(AuditedModelSerializer):
<<<<<<< HEAD
    """HR-facing serializer for grade/entitlement rules."""
=======
    """HR-facing serializer for grade/entitlement rules.

    An entitlement is an **annual leave** entitlement, so ``leave_type`` is
    read-only: saving a band provisions the annual leave type and its first rule
    (:func:`~leave.services.provision_annual_leave`) rather than naming a type
    the caller picked. The field is kept because it is what makes the granted
    type readable — the employee catalog, the entitlement table and the audit
    trail all resolve through it — and because a row written before the field
    existed still has to render.
    """

    target_type = AuditEntry.TargetType.ENTITLEMENT
    # ``leave_type`` is audited rather than just ``days``: which type a band
    # grants is the fact that decides what employees can apply for, so a change
    # to it is exactly what an auditor needs to see and an edit to ``days`` is
    # not enough to explain.
    audit_fields = [
        "grade_start",
        "grade_end",
        "days",
        "effective_from",
        "leave_type",
    ]

    leave_type_name = serializers.CharField(
        source="leave_type.name", read_only=True, default=None
    )
>>>>>>> feature/plans-teams

    audit_prefix = "grade_entitlement"
    audit_fields = ["grade_start", "grade_end", "days", "effective_from"]

    class Meta:
        model = GradeEntitlement
        fields = [
            "id",
            "grade_start",
            "grade_end",
            "days",
            "effective_from",
            "leave_type",
            "leave_type_name",
        ]
        read_only_fields = ["leave_type"]

    def validate(self, attrs: dict) -> dict:
        grade_start = normalize_grade(self._value(attrs, "grade_start"))
        grade_end = normalize_grade(self._value(attrs, "grade_end"))
        effective_from = self._value(attrs, "effective_from")
        days = self._value(attrs, "days")
        # Overlap is checked against the type this band will grant. On create
        # that is the annual type provisioning has not yet written, so resolve
        # the existing one to compare against; on edit it is the band's own.
        leave_type = self.instance.leave_type if self.instance else None
        leave_type = leave_type or find_annual_leave_type()

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
        self._validate_no_overlap(grade_start, grade_end, leave_type)

        return attrs

    def _validate_no_overlap(
        self, grade_start: str, grade_end: str, leave_type
    ) -> None:
        exclude_pk = self.instance.pk if self.instance is not None else None
        overlapping = find_overlapping_rule(
            grade_start, grade_end, leave_type=leave_type, exclude_pk=exclude_pk
        )
        if overlapping is not None:
            granted = (
                f" for {leave_type.name}" if leave_type is not None else ""
            )
            raise serializers.ValidationError(
                {
                    "grade_start": (
                        f"This grade range is already granted{granted} by "
                        f"{overlapping.grade_start}–{overlapping.grade_end} "
                        f"(effective {overlapping.effective_from.isoformat()})."
                    )
                }
            )

    def create(self, validated_data):
        with transaction.atomic():
            validated_data["leave_type"] = provision_annual_leave(
                effective_from=validated_data["effective_from"],
                days=validated_data["days"],
                actor=current_actor(self),
            )
            return super().create(validated_data)

<<<<<<< HEAD
class LeaveTypeSerializer(AuditedModelSerializer):
    """HR-facing serializer for leave types (registry entries)."""

    audit_prefix = "leave_type"
    audit_fields = ["name", "code"]
=======

class LeaveTypeSerializer(AuditedModelSerializer):
    """HR-facing serializer for leave types (registry entries)."""

    target_type = AuditEntry.TargetType.LEAVE_TYPE
    audit_fields = ["name", "code", "is_active"]
>>>>>>> feature/plans-teams

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "is_active",
        ]

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

        self._reject_annual_leave(name, effective_code)

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

    def _reject_annual_leave(self, name: str, effective_code: str) -> None:
        """Refuse to create or rename the canonical annual leave type.

<<<<<<< HEAD
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
=======
        Annual leave is not a registry entry HR curates here: it is provisioned
        by saving an entitlement (:func:`~leave.services.provision_annual_leave`)
        and it is edited by editing that entitlement. Two guards are needed and
        they are different failures.

        *Editing* the existing annual type is refused on **any** field, because
        a partially-editable type is a trap — ``is_active`` looks like an
        ordinary flag and retiring annual leave silently empties every
        employee's leave selection.

        *Creating* something that would become the annual type is refused on the
        identity of the row, so HR cannot make a second, competing "Annual
        Leave" and leave :func:`~leave.services.find_annual_leave_type` to pick
        between them.
        """
        if self.instance is not None:
            if is_annual_leave_type(self.instance):
                raise serializers.ValidationError(
                    {
                        "name": (
                            "Annual leave is created and maintained from "
                            "Entitlements, not from Leave Types. Edit the "
                            "entitlement for the grade range to change the days "
                            "an employee is granted."
                        )
                    }
                )
            return

        if is_annual_leave_identity(name, effective_code):
            field = "code" if effective_code in ANNUAL_LEAVE_CODES else "name"
            raise serializers.ValidationError(
                {
                    field: (
                        f'"{name}" is reserved for annual leave, which is '
                        "created automatically when you add an entitlement. Add "
                        "an entitlement instead, or name a different leave type."
                    )
                }
            )


class EmployeeLeaveTypeSerializer(serializers.ModelSerializer):
    """Read-only, employee-facing view of leave types.

    Resolves ``max_duration_days`` and ``requires_supporting_document`` from
    the currently effective ``LeaveRule`` so employees see the live policy
    instead of a hard-coded list.

    ``entitlement_days`` is the effective days granted to the viewer's grade by
    this type, so the selection can display "X days" without making the employee
    cross-reference the balance card.
    """

    max_duration_days = serializers.SerializerMethodField()
    requires_supporting_document = serializers.SerializerMethodField()
    entitlement_days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "max_duration_days",
            "requires_supporting_document",
            "entitlement_days",
        ]

    def get_max_duration_days(self, obj: LeaveType):
        rule = resolve_leave_rule(obj)
        return rule.max_duration_days if rule else None

    def get_requires_supporting_document(self, obj: LeaveType):
        rule = resolve_leave_rule(obj)
        return rule.requires_supporting_document if rule else False

    def get_entitlement_days(self, obj: LeaveType):
        request = self.context.get("request")
        grade = None
        if request is not None:
            profile = getattr(request.user, "employee_profile", None)
            grade = getattr(profile, "grade", None) if profile else None
        entitlement = resolve_grade_entitlement(
            grade, leave_type=obj, as_of=None
        ) if grade else None
        return entitlement.days if entitlement else None


class LeaveRuleSerializer(AuditedModelSerializer):
    """HR-facing serializer for effective-dated leave rules."""

    target_type = AuditEntry.TargetType.LEAVE_RULE
    audit_fields = [
        "leave_type_id",
        "max_duration_days",
        "eligibility",
        "eligibility_rules",
        "min_notice_days",
        "requires_supporting_document",
        "consumes_annual_entitlement",
>>>>>>> feature/plans-teams
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

<<<<<<< HEAD
    audit_prefix = "financial_year"
=======
    target_type = AuditEntry.TargetType.FINANCIAL_YEAR
>>>>>>> feature/plans-teams
    audit_fields = ["start_date", "end_date", "is_active"]

    class Meta:
        model = FinancialYear
        fields = ["id", "start_date", "end_date", "is_active"]

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

<<<<<<< HEAD
    audit_prefix = "public_holiday"
=======
    target_type = AuditEntry.TargetType.PUBLIC_HOLIDAY
>>>>>>> feature/plans-teams
    audit_fields = ["name", "date"]

    class Meta:
        model = PublicHoliday
        fields = ["id", "name", "date"]

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
<<<<<<< HEAD
    replaced_by_name = serializers.CharField(
        source="replaced_by.file_name", read_only=True, default=None
    )
=======
    """Employee-facing view of a supporting document.

    ``file_url`` is a freshly signed URL derived from the internal
    ``file_path`` at read time; ``file_path`` itself is never serialized.
    Retrospective fields (``status``, ``retired_at``, ``retire_reason``,
    ``retired_by``, ``replaced_by``) are present so the document list endpoint
    can render the archive when ``?include_retired=true``.
    """

    file_url = serializers.SerializerMethodField()
    retired_by = serializers.SerializerMethodField()
    replaced_by = serializers.SerializerMethodField()
>>>>>>> feature/plans-teams

    class Meta:
        model = SupportingDocument
        fields = [
            "id",
            "file_url",
            "file_name",
            "file_size",
            "content_type",
            "uploaded_at",
            "status",
            "retired_at",
<<<<<<< HEAD
            "retired_by",
            "retire_reason",
            "replaced_by",
            "replaced_by_name",
=======
            "retire_reason",
            "retired_by",
            "replaced_by",
>>>>>>> feature/plans-teams
        ]
        read_only_fields = fields

    def get_file_url(self, obj) -> str:
        return safe_signed_document_url(obj.file_path, fallback=obj.file_url)

    def get_retired_by(self, obj):
        if obj.retired_by is None:
            return None
        return {
            "id": obj.retired_by_id,
            "name": obj.retired_by.get_full_name() or obj.retired_by.username,
        }

    def get_replaced_by(self, obj):
        if obj.replaced_by is None:
            return None
        return {"id": str(obj.replaced_by_id), "file_name": obj.replaced_by.file_name}


class LeaveApplicationSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()

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

    def get_documents(self, obj) -> list:
        """The active working set; retired rows are never nested here."""
        return SupportingDocumentSerializer(
            obj.documents.filter(status="active"), many=True
        ).data
