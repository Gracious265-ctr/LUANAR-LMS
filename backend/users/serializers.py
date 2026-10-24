from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from audit.models import AuditEntry
from audit.services import changed_fields, current_actor, record_audit
from teams.models import Team
from roles.services import approver_role_codes_for

from .models import EmployeeProfile
from .services import request_password_set

User = get_user_model()


class OptionalBooleanField(serializers.BooleanField):
    """A boolean whose absence means "leave it alone", not "False".

    ``BooleanField`` sets ``default_empty_html = False``, which is correct for a
    real HTML form — an unchecked checkbox is absent and means False. It is wrong
    for an optional API field: any client that posts multipart or form-encoded
    (a ``curl -F``, an HTML form, and DRF's own test client by default) sends no
    ``is_active`` at all, and DRF then supplies False. Creating an employee that
    way silently produced a *deactivated* account, which looks like an HR mistake
    and is not one.

    With this subclass an absent value resolves to True — "an account is active
    unless something says otherwise" — while an explicit ``false`` from any format
    still arrives as False. :meth:`EmployeeSerializer.update` additionally checks
    ``initial_data`` so an omitted key cannot flip an account back on either.
    """

    default_empty_html = True


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data."""

    full_name = serializers.SerializerMethodField()
    manages_teams = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name", "is_superuser", "manages_teams"]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()

    def get_manages_teams(self, obj: User) -> bool:
        """Whether the account is the designated manager of at least one team.

        Read-only and server-derived. It rides on the profile payload because
        the sidebar needs it in the first paint — a manager is an ordinary
        ``employee``, so their system role alone cannot tell the rail to offer
        the way into the Workflows module. Imported lazily to keep ``users``
        from importing ``organisation`` (which imports ``users.models``) at
        module load.
        """
        from roles.services import managed_team_ids_for

        return bool(managed_team_ids_for(obj))


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


class PasswordSetRequestSerializer(serializers.Serializer):
    """Serializer for the "I have no password" request.

    Deliberately carries no field beyond the address: whether a link is sent is
    not the requester's business, and a response that varied would turn this into
    an account-enumeration oracle.
    """

    email = serializers.EmailField()


class PasswordSetValidateSerializer(serializers.Serializer):
    """Serializer for the pre-flight check the set-password page calls."""

    token = serializers.CharField(max_length=200, trim_whitespace=False)


class PasswordSetConfirmSerializer(serializers.Serializer):
    """Serializer for setting a new password.

    ``validate_password`` runs against the *account's* validators in the service
    (it needs the user object for the similarity check), so this only enforces
    that something was actually submitted.
    """

    token = serializers.CharField(max_length=200, trim_whitespace=False)
    password = serializers.CharField(write_only=True, allow_blank=False)


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing a password from a live session.

    Two rules that are cheap here and would be a real gap if left out:

    * the current password is required, so a stolen access token on its own
      cannot take the account over — it is checked in the service, against the
      stored hash;
    * the confirmation must match, so a typo in a field the user cannot see is
      caught before it becomes their password.

    Strength is deliberately *not* checked here. ``validate_password`` needs the
    user object and runs in the service, alongside the check that the new value
    differs from the current one, so that all three password problems report
    through one code path.
    """

    current_password = serializers.CharField(write_only=True, allow_blank=False)
    new_password = serializers.CharField(write_only=True, allow_blank=False)
    confirm_password = serializers.CharField(write_only=True, allow_blank=False)

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The two passwords do not match."}
            )
        return attrs


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
    is_active = OptionalBooleanField(source="user.is_active", required=False)
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
        """Stop the directory from granting system access.

        A new employee is a *normal employee*, and neither ``approver`` (which
        follows from a workflow appointment) nor ``hr`` (which only a superuser
        grants from the Django admin) may be chosen here. Any *change* of system
        access is likewise an administrator's decision, not HR's.

        Note what is deliberately absent: there is no password rule. HR does not
        set this person's password. An unusable one is issued and a set-password
        link is mailed to the address on file, so requiring one here would only
        reintroduce the HR-knows-everyone's-credentials habit that the
        self-service flow exists to remove.
        """
        super().validate(attrs)

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
                # HR is not told this person's password. The account is issued
                # without a usable one and a set-password link is mailed to the
                # address on file; see the module docstring in services.py.
                user.set_unusable_password()
                user.save()

            instance = EmployeeProfile.objects.create(user=user, **validated_data)
            self._audit(instance, action=AuditEntry.Action.CREATED, before=None)

            # A new account cannot sign in until someone sets its password, and
            # this is the moment HR has just made one: mail the link here rather
            # than leaving it to a manual step HR will forget. Queued, not sent
            # inline, and only while the account still has no usable password —
            # attaching an existing person's employee record must never mail
            # them a reset link.
            if not user.has_usable_password():
                request_password_set(user.email, actor=current_actor(self))
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
                # ``is_active`` is checked against the submitted data as well as
                # the validated data: DRF fills the key in for form-encoded
                # requests, and a PATCH that never mentioned it must not change
                # whether the account is active.
                if field not in user_data:
                    continue
                if field == "is_active" and "is_active" not in self.initial_data:
                    continue
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
