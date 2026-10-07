from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from audit.models import AuditEntry
from audit.services import changed_fields, current_actor, record_audit
from workflows.models import Team
from workflows.services import approver_role_codes_for

from .models import EmployeeProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name", "is_superuser"]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()


class AdminUserSerializer(serializers.ModelSerializer):
    """The superuser's view of an HR account, and the payload that creates one.

    Only two facts make an account an HR account: it is active, and its system
    role is ``hr``. The superuser chooses the person and sets their first
    password; the role itself is not a field the browser can ask for, so this
    endpoint cannot be used to mint another superuser or to promote a normal
    employee. That is the whole point of keeping the bootstrap administrator
    outside ``User.Role``: the product can grant HR access and nothing higher.
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        help_text=(
            "The account's initial password. Required when creating an HR user; "
            "on update, a blank value keeps the current password and a non-blank "
            "value resets it. Never returned."
        ),
    )
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "is_superuser",
            "password",
        ]
        read_only_fields = ["role", "is_superuser"]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()

    def validate_email(self, value: str) -> str:
        value = value.lower()
        clash = (
            User.objects.filter(Q(email__iexact=value) | Q(username__iexact=value))
            .exclude(pk=getattr(self.instance, "pk", None))
            .first()
        )
        if clash is not None:
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError(
                {
                    "password": (
                        "Set an initial password for this HR user. They sign in "
                        "with their email and this password."
                    )
                }
            )
        if password and len(password) < 8:
            raise serializers.ValidationError(
                {"password": "Use at least 8 characters."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password", "")
        email = validated_data["email"]
        with transaction.atomic():
            user = User(
                username=email,
                email=email,
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                is_active=validated_data.get("is_active", True),
                role=User.Role.HR,
            )
            user.set_password(password)
            user.save()
        return user

    def update(self, instance: User, validated_data: dict) -> User:
        password = validated_data.pop("password", "")
        with transaction.atomic():
            if "email" in validated_data:
                instance.email = validated_data["email"]
                instance.username = validated_data["email"]
            for field in ("first_name", "last_name", "is_active"):
                if field in validated_data:
                    setattr(instance, field, validated_data[field])
            if password:
                instance.set_password(password)
            instance.save()
        return instance


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
        help_text=(
            "What the account can reach in the product. A new employee starts as "
            "a normal employee and cannot be created as an approver; approver "
            "access follows from the workflow stage HR appoints them to."
        ),
    )
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        help_text=(
            "The account's initial password, set by HR. Required when creating "
            "an employee; on update, a blank value keeps the current password "
            "and a non-blank value resets it. Never returned."
        ),
    )
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
        help_text="The team whose approval chain this employee submits into.",
    )
    team_name = serializers.CharField(source="team.name", read_only=True)
    approver_roles = serializers.SerializerMethodField()

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
            "password",
            "approver_roles",
            "designation",
            "faculty",
            "category",
            "gender",
            "grade",
            "appointment_date",
            "team",
            "team_name",
            "is_active",
        ]

    def get_approver_roles(self, obj: EmployeeProfile) -> list[str]:
        """The approver positions this person holds, from the role graph.

        Empty for an ordinary employee. HR reads it to answer "who can approve
        for this person", which ``role`` can no longer answer: it is a system
        access level, not a place in a chain.
        """
        return approver_role_codes_for(obj.user)

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

    def validate(self, attrs: dict) -> dict:
        """Enforce who may hold which account, and that a password is set.

        Two rules live here rather than in the view:

        * **A password is required on create** and must be at least eight
          characters. HR is the source of credentials, so a directory entry that
          cannot log in is not a successful create.
        * **The role cannot be escalated through the directory.** A new employee
          is a *normal employee*, and neither ``approver`` (which follows from a
          workflow appointment) nor ``hr`` (which only a superuser grants from
          the Django admin) may be chosen here.
        """
        super().validate(attrs)

        password = attrs.get("password")
        if self.instance is None:
            if not password:
                raise serializers.ValidationError(
                    {
                        "password": (
                            "Set an initial password for this person. They sign "
                            "in with their email and this password."
                        )
                    }
                )
        if password and len(password) < 8:
            raise serializers.ValidationError(
                {"password": "Use at least 8 characters."}
            )

        user_data = attrs.get("user") or {}
        requested_role = user_data.get("role")
        if self.instance is None:
            if requested_role in (User.Role.APPROVER, User.Role.HR):
                raise serializers.ValidationError({"role": self._role_refusal()})
        elif requested_role and requested_role != self.instance.user.role:
            # Any *change* of system access is an administrator's decision, not
            # HR's: HR neither grants nor revokes the approval desk or HR reach
            # from the directory. An unchanged value is accepted so an existing
            # HR or approver account can still have its profile saved.
            raise serializers.ValidationError({"role": self._role_refusal()})
        return attrs

    @staticmethod
    def _role_refusal() -> str:
        return (
            "The directory creates normal employees. Approver access follows "
            "from the workflow stage HR appoints them to, and an HR account is "
            "created by an administrator."
        )

    def create(self, validated_data: dict) -> EmployeeProfile:
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", "")
        email = user_data["email"]

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
                    role=User.Role.EMPLOYEE,
                    is_active=user_data.get("is_active", True),
                )

            # HR set this password explicitly, whether the account is new or an
            # existing email that is being given an employee record.
            user.set_password(password)
            user.save()

            instance = EmployeeProfile.objects.create(user=user, **validated_data)
            self._audit(instance, action=AuditEntry.Action.CREATED, before=None)
        return instance

    def update(self, instance: EmployeeProfile, validated_data: dict) -> EmployeeProfile:
        before = self._snapshot(instance)
        user_data = validated_data.pop("user", {})
        # Popped before the profile loop below: a password is a property of the
        # linked user, not a column on EmployeeProfile, and `password` is never
        # written through `setattr` on the profile.
        password = validated_data.pop("password", "")
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

            if password:
                user.set_password(password)

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
            "faculty": instance.faculty,
            "category": instance.category,
            "gender": instance.gender,
            "grade": instance.grade,
            "appointment_date": instance.appointment_date,
            "team": instance.team_id,
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
