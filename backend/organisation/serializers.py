"""Organisation-owned serializers for approver roles, holdings, and campuses.

Covers approver-role administration, role assignments (institution-, team-, and
campus-scoped), and campus administration.
"""

from django.utils.text import slugify
from rest_framework import serializers

from users.models import User

from workflows.models import Workflow
from .models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    RoleAssignment,
)
from .services import (
    create_approver_role,
    create_campus,
    create_campus_role_assignment,
    create_role_assignment,
    deactivate_approver_role,
    role_usage_map,
    update_approver_role,
    update_campus,
)


class ApproverRoleSerializer(serializers.ModelSerializer):
    """One HR-managed approver role.

    Reads expose the derived ``is_in_use`` and ``usage`` so the Roles list can
    say *why* a role cannot be deactivated without HR cross-referencing other
    screens. Writes never go through the model directly: ``create``/
    ``update``/``destroy`` delegate to the transactional services so the audit
    trail and the in-use guard are impossible to bypass from the API.
    """

    is_in_use = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()

    class Meta:
        model = ApproverRole
        fields = [
            "id",
            "code",
            "label",
            "description",
            "is_active",
            "history_scope",
            "handles_cancellation",
            "is_institution_wide",
            "is_in_use",
            "usage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["code", "is_in_use", "usage", "created_at", "updated_at"]

    def _usage_for(self, instance: ApproverRole) -> list[str]:
        """The usage clauses for ``instance``, computed once for the request.

        ``is_in_use`` and ``usage`` expose the same fact, and the Roles screen
        asks for it for every role at once. Computing it per field, per role,
        made the list cost one query per blocker per role; this resolves the
        whole page in three queries and reads the result from the shared
        serializer context on every subsequent field.
        """
        cache = self.context.get("role_usage")
        if cache is None:
            siblings = getattr(self.parent, "instance", None)
            subjects = list(siblings) if getattr(self.parent, "many", False) else [self.instance]
            cache = role_usage_map(subjects)
            self.context["role_usage"] = cache
        return cache.get(instance.pk, [])

    def get_is_in_use(self, instance: ApproverRole) -> bool:
        return bool(self._usage_for(instance))

    def get_usage(self, instance: ApproverRole) -> list[str]:
        return self._usage_for(instance)

    def create(self, validated_data: dict) -> ApproverRole:
        return create_approver_role(
            actor=self.context["actor"], data=dict(validated_data)
        )

    def update(self, instance: ApproverRole, validated_data: dict) -> ApproverRole:
        return update_approver_role(
            role=instance, actor=self.context["actor"], data=dict(validated_data)
        )

    def destroy(self, instance: ApproverRole) -> None:
        """Deactivate rather than delete.

        Roles are referenced by workflow stages, team memberships, and every
        historical stage snapshot, so hard deletion is never safe. A role also
        cannot be deactivated while it is still in use, so this doubles as the
        retire action and surfaces that refusal to the caller.
        """
        deactivate_approver_role(role=instance, actor=self.context["actor"])


class ApproverRoleWriteSerializer(serializers.Serializer):
    """Create a role from its name; update it by editing its behaviour.

    ``label`` is the only thing a new role needs, and ``code`` is not accepted:
    it is derived from the name (see
    :func:`workflows.services.role_code_from_name`) so the identifier every rule
    reads cannot drift from the name every screen shows.

    On update, ``label`` is not accepted either — a role's name is what
    historical stages and audit entries quote, and renaming it would make those
    quote something that no longer exists. The behavioural fields are editable
    here because they are decisions rather than identity: who may see history,
    whether the role decides cancellations, whether it may be held
    institution-wide.

    ``is_active`` is read-only on purpose. Retirement is the DELETE verb, which
    runs the in-use guard; accepting it here would let a PATCH retire a role an
    active workflow, team, or holder still depends on.
    """

    label = serializers.CharField(
        max_length=80,
        required=False,
        help_text="The role's name, as it appears wherever the role is chosen.",
    )
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    is_active = serializers.BooleanField(read_only=True)
    history_scope = serializers.ChoiceField(
        choices=ApproverRole.HistoryScope.choices, required=False
    )
    handles_cancellation = serializers.BooleanField(required=False)
    is_institution_wide = serializers.BooleanField(required=False)

    def validate(self, attrs: dict) -> dict:
        if self.instance is not None:
            if "label" in attrs and attrs["label"] != self.instance.label:
                raise serializers.ValidationError(
                    {
                        "label": [
                            "A role's name cannot be changed once it exists. "
                            "Workflow stages and past decisions quote it. Create a "
                            "new role instead and retire this one."
                        ]
                    }
                )
            return attrs
        if not attrs.get("label", "").strip():
            raise serializers.ValidationError({"label": ["Enter a role name."]})
        return attrs

    def create(self, validated_data: dict) -> ApproverRole:
        return create_approver_role(
            actor=self.context["actor"], data=dict(validated_data)
        )

    def update(self, instance: ApproverRole, validated_data: dict) -> ApproverRole:
        return update_approver_role(
            role=instance, actor=self.context["actor"], data=dict(validated_data)
        )


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """A person's institution-wide role holding."""

    # Not filtered on is_active: the service rejects an inactive account with a
    # sentence HR can act on, which beats DRF's "Invalid pk ... does not exist".
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.PrimaryKeyRelatedField(
        queryset=ApproverRole.objects.all()
    )
    user_name = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_name",
            "role",
            "role_label",
            "created_at",
        ]
        read_only_fields = ["created_at"]
        # Held to the same rule as team memberships: the service owns uniqueness
        # so the error says who already holds the role.
        validators: list = []

    def get_user_name(self, instance: RoleAssignment) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_role_label(self, instance: RoleAssignment) -> str:
        return instance.role.label

    def validate(self, attrs: dict) -> dict:
        # No scope guard here: assigning a team role its first institution-wide
        # holder is exactly how a role *becomes* institution-wide. The service
        # owns the real refusals (role already held on a team or campus, role
        # deactivated, user inactive or already a wide approver).
        return attrs

    def create(self, validated_data: dict) -> RoleAssignment:
        return create_role_assignment(
            user=validated_data["user"],
            role=validated_data["role"],
            actor=self.context["actor"],
        )


class CampusSerializer(serializers.ModelSerializer):
    """HR-maintained campus reference data, used to scope teams."""

    class Meta:
        model = Campus
        fields = ["id", "name", "code", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_code(self, value: str) -> str:
        cleaned = slugify(value)
        if not cleaned:
            raise serializers.ValidationError(
                "The campus code must be made of letters, numbers, or hyphens."
            )
        if cleaned != value:
            raise serializers.ValidationError(
                f'Use lowercase letters, numbers, and hyphens only, like "{cleaned}".'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        if self.instance is not None:
            return attrs
        code = attrs.get("code")
        if code and Campus.objects.filter(code=code).exists():
            raise serializers.ValidationError(
                {"code": [f'The campus code "{code}" is already in use.']}
            )
        return attrs

    def create(self, validated_data: dict) -> Campus:
        return create_campus(actor=self.context["actor"], data=dict(validated_data))

    def update(self, instance: Campus, validated_data: dict) -> Campus:
        return update_campus(
            campus=instance, actor=self.context["actor"], data=dict(validated_data)
        )


class WideRoleAssignmentSerializer(serializers.ModelSerializer):
    """Shared shape of the team- and campus-wide holding screens.

    Deliberately the same three fields as the institution-wide one — an
    employee, a role, and the scope it is held at — so "who approves what" is
    configured the same way wherever it is configured. The service owns
    uniqueness, so saving a second holder for the same role and scope replaces
    the first rather than failing; the validator list is emptied for the same
    reason the institution-wide one is.
    """

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.PrimaryKeyRelatedField(
        queryset=ApproverRole.objects.all()
    )
    user_name = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    def get_user_name(self, instance) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_role_label(self, instance) -> str:
        return instance.role.label

    def validate_role(self, value: ApproverRole) -> ApproverRole:
        if not value.is_active:
            raise serializers.ValidationError(
                f'"{value.label}" is deactivated. Reactivate it in Roles, or '
                "pick an active role."
            )
        if value.is_institution_wide:
            raise serializers.ValidationError(
                f'"{value.label}" is an institution-wide role. Assign its '
                "holder under Approvers, not here."
            )
        return value

    def validate_user(self, value: User) -> User:
        if not value.is_active:
            raise serializers.ValidationError(
                f"{value.get_full_name() or value.username} is not an active "
                "user. Activate the account before assigning a role."
            )
        if getattr(value, "employee_profile", None) is None:
            raise serializers.ValidationError(
                f"{value.get_full_name() or value.username} has no employee "
                "record, so there is nothing to hold an approver role with. "
                "Complete their employee record first."
            )
        return value



class CampusRoleAssignmentSerializer(WideRoleAssignmentSerializer):
    """One campus-wide holding, which reaches every team at that campus."""

    class Meta:
        model = CampusRoleAssignment
        fields = [
            "id",
            "campus",
            "role",
            "user",
            "user_name",
            "role_label",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        validators: list = []

    def create(self, validated_data: dict) -> CampusRoleAssignment:
        return create_campus_role_assignment(
            campus=validated_data["campus"],
            role=validated_data["role"],
            user=validated_data["user"],
            actor=self.context["actor"],
        )


