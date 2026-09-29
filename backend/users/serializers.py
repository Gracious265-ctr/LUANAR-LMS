from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from audit.models import AuditEntry
from audit.services import changed_fields, current_actor, record_audit

from .models import EmployeeProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name"]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()


class LoginSerializer(serializers.Serializer):
    """Serializer for login endpoint."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class EmployeeSerializer(serializers.ModelSerializer):
    """HR-facing serializer for employee records and their linked account."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(
        source="user.first_name", required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        source="user.last_name", required=False, allow_blank=True
    )
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    role = serializers.ChoiceField(
        choices=User.Role.choices,
        source="user.role",
        required=False,
        allow_blank=True,
    )
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    supervisor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text="The employee's assigned supervisor (used to resolve the workflow supervisor stage).",
    )

    class Meta:
        model = EmployeeProfile
        fields = [
            "id",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "designation",
            "department",
            "faculty",
            "category",
            "gender",
            "grade",
            "appointment_date",
            "supervisor",
            "is_active",
        ]

    def validate_email(self, value: str) -> str:
        value = value.lower()
        candidate = User.objects.filter(
            Q(email__iexact=value) | Q(username__iexact=value)
        ).first()

        if candidate is None:
            return value

        if (
            self.instance is None or self.instance.user != candidate
        ) and EmployeeProfile.objects.filter(user=candidate).exists():
            raise serializers.ValidationError(
                "An employee record for this email already exists."
            )

        if self.instance is not None and self.instance.user.pk != candidate.pk:
            raise serializers.ValidationError("A user with this email already exists.")

        return value

    def create(self, validated_data: dict) -> EmployeeProfile:
        user_data = validated_data.pop("user", {})
        email = user_data["email"]
        role = user_data.get("role") or User.Role.EMPLOYEE

        with transaction.atomic():
            user = User.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).first()

            if user is None:
                user = User(
                    username=email,
                    email=email,
                    first_name=user_data.get("first_name", ""),
                    last_name=user_data.get("last_name", ""),
                    role=role,
                    is_active=user_data.get("is_active", True),
                )
                user.set_unusable_password()
                user.save()

            instance = EmployeeProfile.objects.create(user=user, **validated_data)
            self._audit(instance, action=AuditEntry.Action.CREATED, before=None)
        return instance

    def update(self, instance: EmployeeProfile, validated_data: dict) -> EmployeeProfile:
        before = self._snapshot(instance)
        user_data = validated_data.pop("user", {})
        user = instance.user

        with transaction.atomic():
            if "email" in user_data:
                user.email = user_data["email"]
                user.username = user_data["email"]

            for field in ("first_name", "last_name", "is_active"):
                if field in user_data:
                    setattr(user, field, user_data[field])

            if "role" in user_data:
                user.role = user_data["role"] or User.Role.EMPLOYEE

            user.save()

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            after = self._snapshot(instance)
            self._audit(
                instance,
                action=AuditEntry.Action.UPDATED,
                before=before,
                after=after,
            )
        return instance

    def _snapshot(self, instance: EmployeeProfile) -> dict:
        user = instance.user
        return {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "designation": instance.designation,
            "department": instance.department,
            "faculty": instance.faculty,
            "category": instance.category,
            "gender": instance.gender,
            "grade": instance.grade,
            "appointment_date": instance.appointment_date,
            "supervisor_id": instance.supervisor_id,
        }

    def _audit(
        self,
        instance: EmployeeProfile,
        *,
        action: str,
        before: dict | None,
        after: dict | None = None,
    ) -> None:
        actor = current_actor(self)
        if actor is None:
            return
        detail = {"before": None, "after": after or self._snapshot(instance)}
        if before is not None:
            detail = changed_fields(before, after or self._snapshot(instance))
        record_audit(
            actor=actor,
            action=action,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=instance.pk,
            target_summary=instance.user.get_full_name(),
            detail=detail,
        )