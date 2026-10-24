from rest_framework import serializers

from .models import Campus, CampusRoleAssignment
from roles.models import ApproverRole
from teams.models import Team, TeamRoleAssignment
from users.models import User


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


class TeamRoleAssignmentSerializer(WideRoleAssignmentSerializer):
    """One team-wide holding: this role, on this team, held by this person.

    ``is_team_manager`` designates the holder as the team's single designated
    manager, the flag the team's members and chains are run under. It is read
    here and written through the ``set-manager``/``clear-manager`` actions, which
    clear it from any other holder on the team first — so the one-manager-per-team
    rule is the service's, and this shape only reports it.
    """

    class Meta:
        model = TeamRoleAssignment
        fields = [
            "id",
            "team",
            "role",
            "user",
            "user_name",
            "role_label",
            "is_team_manager",
            "created_at",
        ]
        read_only_fields = ["id", "is_team_manager", "created_at"]
        validators: list = []

    def create(self, validated_data: dict) -> TeamRoleAssignment:
        return create_team_role_assignment(
            team=validated_data["team"],
            role=validated_data["role"],
            user=validated_data["user"],
            actor=self.context["actor"],
        )


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


