from __future__ import annotations

from django.utils.text import slugify
from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from leave_config.models import LeaveType
from leave_config.services import (
    ANNUAL_LEAVE_CODES,
    is_annual_leave_identity,
    is_annual_leave_type,
    normalize_leave_code,
)

__all__ = ["LeaveTypeSerializer"]


class LeaveTypeSerializer(AuditedModelSerializer):
    """Write/read shape for a leave type and every rule attached to it.

    ``eligible_grades`` is a plain list of grade ids (§1.4) normalised on the
    way in — the value is stored exactly as :meth:`LeaveType.eligible_grade_ids`
    reads it back, so no two callers can disagree about casing or padding.
    There is deliberately no days-per-year field (§1.3); entitlement is
    grade-based and lives in the Staff Members app's mapping.
    """

    target_type = AuditEntry.TargetType.LEAVE_TYPE
    audit_fields = [
        "name",
        "code",
        "color",
        "branch_scope",
        "eligible_grades",
        "eligible_gender",
        "requires_supporting_document",
        "max_duration_days",
        "notice_days",
        "plannable",
        "requires_institutional_registrar_approval",
        "is_active",
    ]

    eligible_grades = serializers.ListField(
        # Blank entries are a slip of the pencil rather than a grade id, so they
        # are accepted here and dropped by ``validate_eligible_grades`` below.
        child=serializers.CharField(max_length=40, allow_blank=True),
        required=False,
        help_text=(
            "Grade ids this type is limited to; empty or omitted means every "
            "grade is eligible."
        ),
    )

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "color",
            "description",
            "branch_scope",
            "eligible_grades",
            "eligible_gender",
            "requires_supporting_document",
            "max_duration_days",
            "notice_days",
            "eligibility",
            "eligibility_rules",
            "consumes_annual_entitlement",
            "plannable",
            "requires_institutional_registrar_approval",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    # -- Field validation ---------------------------------------------------

    def validate_eligible_grades(self, value) -> list[str]:
        """Strip, upper-case and de-duplicate grade ids, preserving order."""
        seen: set[str] = set()
        normalised: list[str] = []
        for raw in value:
            grade_id = str(raw).strip().upper()
            if not grade_id or grade_id in seen:
                continue
            seen.add(grade_id)
            normalised.append(grade_id)
        return normalised

    def validate(self, attrs: dict) -> dict:
        name = (self._value(attrs, "name") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        # A blank code is derived from the name, matching the model's save().
        effective_code = normalize_leave_code(self._value(attrs, "code"))
        effective_code = effective_code or slugify(name)
        if not effective_code:
            raise serializers.ValidationError(
                {"name": "Name must contain letters or numbers."}
            )
        attrs["code"] = effective_code

        self._guard_annual_leave(attrs, name, effective_code)

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

    def _guard_annual_leave(
        self, attrs: dict, name: str, effective_code: str
    ) -> None:
        """Keep the annual type's identity — and its entitlement marker — fixed.

        Annual leave is not a registry entry HR builds from scratch: it is
        provisioned by saving an entitlement (:func:`~leave_config.services.
        provision_annual_leave`). Its **rules** are HR's to edit here, which is
        the only surface that owns them since the Leave Rules screens were
        retired. Three things must not move:

        * *Creating* a row that would become the annual type is refused on its
          identity, so HR cannot make a second, competing "Annual Leave" and
          leave :func:`~leave_config.services.find_annual_leave_type` to pick
          between them.
        * *Renaming* the provisioned annual type is refused for the same reason:
          the row is found by name/code, so a rename would hide it from
          provisioning and orphan every entitlement that points at it. Its
          ``is_active`` is separately read-only, and the deactivate/reactivate
          endpoints refuse the annual type outright, so it cannot be retired
          from here either.
        * The ``consumes_annual_entitlement`` marker is what makes the balance
          ledger resolve to this type
          (``leave.services.resolve_annual_balance_entitlement``); clearing it
          would silently empty the annual ring. It is not a field this form
          offers, so an attempt to move it is reported at the form level.
        """
        if self.instance is None:
            if is_annual_leave_identity(name, effective_code):
                field = "code" if effective_code in ANNUAL_LEAVE_CODES else "name"
                raise serializers.ValidationError(
                    {
                        field: (
                            f'"{name}" is reserved for annual leave, which is '
                            "created automatically when you add an entitlement. "
                            "Add an entitlement instead, or name a different "
                            "leave type."
                        )
                    }
                )
            return

        if not is_annual_leave_type(self.instance):
            return

        if name != self.instance.name:
            raise serializers.ValidationError(
                {
                    "name": (
                        "Annual leave is found by its name, so it cannot be "
                        "renamed. Edit its rules here, or change how many days "
                        "a grade range is granted by editing its entitlement."
                    )
                }
            )
        if effective_code != self.instance.code:
            raise serializers.ValidationError(
                {
                    "code": (
                        "Annual leave is found by its short code, so that cannot "
                        "be changed."
                    )
                }
            )
        if (
            "consumes_annual_entitlement" in attrs
            and attrs["consumes_annual_entitlement"]
            != self.instance.consumes_annual_entitlement
        ):
            raise serializers.ValidationError(
                "Annual leave always draws down the annual leave balance; that "
                "cannot be changed here."
            )

    def validate_max_duration_days(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Maximum duration must be at least 1 day.")
        return value

    def validate_notice_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Notice period cannot be negative.")
        return value

    def validate_eligibility_rules(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Eligibility rules must be a list.")
        for rule in value:
            if not isinstance(rule, dict) or "type" not in rule:
                raise serializers.ValidationError(
                    "Each eligibility rule must be an object with a 'type'."
                )
        return value
