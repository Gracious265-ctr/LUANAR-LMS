from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from audit.services import current_actor, record_audit

from leave_types.models import LeaveType

from ..models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    SupportingDocument,
)
from ..services import (
    ANNUAL_LEAVE_CODES,
    find_overlapping_financial_year,
    find_overlapping_rule,
    find_annual_leave_type,
    is_annual_leave_identity,
    is_annual_leave_type,
    normalize_grade,
    normalize_leave_code,
    provision_annual_leave,
    resolve_grade_entitlement,
)
from ..services.storage import safe_signed_document_url


class GradeEntitlementSerializer(AuditedModelSerializer):
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
                days=validated_data["days"],
                actor=current_actor(self),
            )
            return super().create(validated_data)


class EmployeeLeaveTypeSerializer(serializers.ModelSerializer):
    """Read-only, employee-facing view of leave types.

    Every rule on here is read straight off ``leave_types.LeaveType`` — the
    registry that owns them (refinement unit 06) — so the catalog shows the live
    policy rather than a hard-coded list.

    ``entitlement_days`` is the effective days granted to the viewer's grade by
    this type, so the selection can display "X days" without making the employee
    cross-reference the balance card. Entitlement itself is grade-based and
    lives in ``leave.GradeLeaveEntitlement``, never on the type (§1.3).
    """

    entitlement_days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "color",
            "description",
            "max_duration_days",
            "requires_supporting_document",
            "entitlement_days",
            # Leave Plans (unit 04) only offer types flagged plannable, and use
            # the notice window to explain when a reminder will fire.
            "plannable",
            "notice_days",
        ]

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


class FinancialYearSerializer(AuditedModelSerializer):
    """HR-facing serializer for configured financial-year periods."""

    target_type = AuditEntry.TargetType.FINANCIAL_YEAR
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
            instance = super().create(validated_data)
            self._settle_active_flag(instance)
        return instance

    def update(self, instance, validated_data: dict):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            self._settle_active_flag(instance)
            instance.refresh_from_db()
        return instance


class SupportingDocumentSerializer(serializers.ModelSerializer):
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
            "retire_reason",
            "retired_by",
            "replaced_by",
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
            "source_plan",
            "created_at",
            "updated_at",
            "submitted_at",
            "documents",
            "rejection_accepted_at",
        ]
        read_only_fields = [
            "id",
            "calculated_days",
            "working_days",
            "calendar_days",
            "financial_year_label",
            "status",
            "reference_number",
            "source_plan",
            "employee",
            "created_at",
            "updated_at",
            "submitted_at",
            "rejection_accepted_at",
        ]

    def get_documents(self, obj) -> list:
        """The active working set; retired rows are never nested here."""
        return SupportingDocumentSerializer(
            obj.documents.filter(status="active"), many=True
        ).data
