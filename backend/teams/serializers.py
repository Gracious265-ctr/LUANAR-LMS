"""Team serializers moved from chains."""

from __future__ import annotations

from rest_framework import serializers

from campuses.models import Campus
from chains.services import (
    StageSequenceError,
    create_team,
    deactivate_team,
    normalize_section_sequence,
    update_team,
    workflow_section_roles,
)
from chains.models import Section, SectionMember, Workflow, WorkflowMember
from roles.models import ApproverRole
from roles.services import (
    _resolve_stage_role,
    add_team_member,
    add_team_members,
    approver_role_codes_for,
    is_team_manager,
)
from teams.models import Team, TeamRoleAssignment
from users.models import EmployeeProfile, User

__all__ = [
    "TeamSerializer",
    "TeamMemberSerializer",
    "TeamRoleAssignmentSerializer",
]


class TeamSectionInputSerializer(serializers.Serializer):
    """One approval step written inline as part of a team.

    A step names the role it needs and the single person who acts for it. Naming
    both here is what lets a team be configured in one pass: HR is not asked to
    save a chain, go and look up its id, and paste it into a team form.

    ``approver`` is one id, not a list. A step has exactly one approver, so the
    wire format says so too — a list here would let a form offer "any of these
    people", which is precisely the configuration the stage model forbids.
    """

    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    approver_role = serializers.CharField(max_length=100)
    order = serializers.IntegerField(required=False, min_value=1)
    approver = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_approver_role(self, value: str) -> str:
        """Resolve the role to a code now, so a bad role fails before any write.

        Returning the code rather than the label keeps the service's normalized
        payload in its documented shape, and a role that is missing or
        deactivated is refused here rather than after a workflow row exists.
        """
        role = _resolve_stage_role(value.strip())
        if role is None:
            raise serializers.ValidationError(
                "That approver role is missing or deactivated. Pick an active "
                "role, or reactivate the role in Roles."
            )
        return role.code


class TeamWorkflowInputSerializer(serializers.Serializer):
    """The approval chain to create alongside a team."""

    name = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        help_text=(
            "Defaults to the team name. Workflow names are unique, so a clash "
            "is suffixed rather than rejected."
        ),
    )
    sections = TeamSectionInputSerializer(many=True)

    def validate_sections(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError(
                "At least one approval step is required."
            )
        # Steps are numbered by the order they appear in. A team form lists them
        # top to bottom, so making HR type a separate number for each one would
        # be a second way of saying the same thing — and a second way to get it
        # wrong. An explicit order is still accepted for clients that send one.
        numbered = [
            {**step, "order": step.get("order") or position}
            for position, step in enumerate(value, start=1)
        ]
        # Reuses the workflow's own sequence rules so a chain written inline is
        # validated identically to one written on the workflow screen, and both
        # get numbered in the order given rather than the order submitted.
        try:
            normalize_section_sequence(numbered)
        except StageSequenceError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})
        return numbered


class WorkflowWriteSerializer(serializers.Serializer):
    """Create a workflow for a team, or edit one's fields and stages.

    ``team`` is required on create — a workflow exists *for* a team, and stage
    rules (an approver must be a member of the team) have nothing to check
    against otherwise. On update, naming the team that already owns it is
    confirmation rather than a move — the edit form restates the team it is
    editing under — and is accepted and discarded. Naming any other team, or
    sending null, is refused: re-pointing a workflow would re-route one team's
    applications into another team's steps, stranding every application inside
    it at a step nobody staffs for them.

    ``sections`` replaces the stage list when supplied, through the same
    sequence rules the team form uses. It may be omitted on create, so HR can
    create the workflow first and configure its stages on the next screen.
    """

    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(), required=False, allow_null=True
    )
    effective_from = serializers.DateField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    sections = TeamSectionInputSerializer(many=True, required=False)
    # The normal-member pool for this workflow: team members who are not
    # section approvers. Written as the whole list so what is saved is what the
    # screen showed; ``None`` on update leaves membership untouched.
    members = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_null=True,
        help_text=(
            "User ids of the normal workflow members. Each must already be a "
            "member of the workflow's team. Omit to leave membership unchanged; "
            "send an empty list to clear it."
        ),
    )

    def validate_sections(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError(
                "At least one approval step is required."
            )
        numbered = [
            {**step, "order": step.get("order") or position}
            for position, step in enumerate(value, start=1)
        ]
        try:
            normalize_section_sequence(numbered)
        except StageSequenceError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})
        return numbered

    def validate(self, attrs: dict) -> dict:
        # A chain does not schedule itself or switch itself off. When it starts
        # applying is when the team that routes through it is activated, and
        # switching a chain off is retiring the team — a decision that has to
        # name the team so the team's own history records why. Accepting a date
        # or a flag here would let a chain say it starts in June while the team
        # routing through it went live in May, with neither screen showing the
        # other. So the field is named, explained, and refused.
        for field, message in (
            (
                "effective_from",
                "A chain does not carry its own start date. When it begins "
                "applying is decided when the team that routes through it is "
                "activated, on the team.",
            ),
            (
                "is_active",
                "A chain is not switched on or off on its own. Activating or "
                "retiring a team decides whether its chain is in force, so it "
                "is done on the team and audited there.",
            ),
            (
                "effective_to",
                "A chain does not carry its own end date either. It runs to the "
                "end of the academic calendar, which is read from the academic "
                "year in force when the chain is created.",
            ),
        ):
            if field in attrs:
                raise serializers.ValidationError({field: [message]})

        if self.instance is None:
            if attrs.get("team") is None:
                raise serializers.ValidationError(
                    {"team": ["A workflow has to be created for a team."]}
                )
        elif "team" in attrs:
            # Naming the workflow's own team is confirmation, not a move: the
            # edit form restates the team it is editing under. Any other team —
            # or null — is a move that would re-route this workflow's
            # applications into another team's steps.
            if (
                attrs["team"] is None
                or attrs["team"].pk != self.instance.team_id
            ):
                raise serializers.ValidationError(
                    {
                        "team": [
                            "A workflow cannot be moved between teams. Create it "
                            "under the team it belongs to."
                        ]
                    }
                )
            attrs.pop("team")
        return attrs

    def create(self, validated_data: dict) -> Workflow:
        return create_workflow(
            team=validated_data.pop("team"),
            actor=self.context["actor"],
            data=dict(validated_data),
        )

    def update(self, instance: Workflow, validated_data: dict) -> Workflow:
        return update_workflow(
            workflow=instance,
            actor=self.context["actor"],
            data=dict(validated_data),
        )


class TeamManagerInputSerializer(serializers.Serializer):
    """The team-wide role holding to designate as a team's manager.

    HR picks a team-scoped approver role and the person who holds it: the role is
    the capability the manager acts with, the person is who acts. Both are
    required — a manager without a role could not approve, and a role without a
    holder names nobody. The role/person/team rules (active, team-scoped, and
    category-matching) are enforced where every other wide holding is, in
    :func:`workflows.services.create_team_role_assignment`.
    """

    role = serializers.PrimaryKeyRelatedField(queryset=ApproverRole.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class TeamSerializer(serializers.ModelSerializer):
    """A team: the routing unit HR assigns people to."""

    def _value(self, attrs: dict, field: str):
        """The submitted value for ``field``, falling back to the stored one.

        A PATCH is validated against the fully-merged state rather than treating
        an absent key as missing, so "only the end date was sent" is checked
        against the start date the team already has.
        """
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    campus = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    # No DRF default, and deliberately so: a field default is filled in before
    # ``validate`` runs, which would make "a campus was sent but no category"
    # indistinguishable from "an administration team was sent". The model's own
    # default still applies on create, and ``validate`` infers the category
    # where the campus says one.
    category = serializers.ChoiceField(
        choices=Team.Category.choices,
        required=False,
        help_text=(
            "Academic teams sit at a campus and may use campus-wide approvers; "
            "administration teams are not campus-based and are the only teams "
            "an institution-wide approver may serve."
        ),
    )
    # Read-only: routing is a decision of its own, made through the ``route``
    # action, so a generic PATCH can never re-route a team.
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    workflows = serializers.SerializerMethodField()
    # The manager to designate, written on create or reassigned on update. A team
    # is handed to a manager, who then holds its day-to-day configuration.
    manager = TeamManagerInputSerializer(write_only=True, required=False)
    # The chain, written inline. On create it is created with the team, so there
    # is never a team that exists pointing at a chain HR has not finished
    # describing. On update it replaces the steps of the chain the team already
    # has. Either way it is the one and only way a chain is written.
    new_workflow = TeamWorkflowInputSerializer(write_only=True, required=False)
    # A team no longer holds members itself — its workflow's sections do. These
    # are flattened for display so the team list can show who is on the team
    # without a second request, but they are derived from the sections, so there
    # is exactly one place a person is recorded as able to act.
    members = serializers.SerializerMethodField()
    stage_roles = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()
    is_effective = serializers.BooleanField(read_only=True)
    # Whether the requesting user is this team's designated manager. It decides
    # the roster and the default chain on the screen, which the API now lets
    # only the manager write, so the UI must not offer HR buttons that would be
    # refused. Read-only and computed, never stored.
    is_team_manager = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "code",
            "description",
            "category",
            "campus",
            "campus_name",
            "workflow",
            "workflow_name",
            "workflows",
            "manager",
            "new_workflow",
            "status",
            "effective_from",
            "effective_to",
            "is_effective",
            "is_team_manager",
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "code",
            # Lifecycle is not editable here: creating a team puts it in force,
            # and retiring it goes through its own audited action rather than a
            # PATCH, so neither can happen by accident or without an audit entry.
            "status",
            "is_effective",
            # Routing is the ``route`` action's, never a field edit.
            "workflow",
            "workflows",
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        # Routing is the ``route`` action's, so a client still sending
        # ``workflow`` on a team write learns the boundary instead of believing
        # it pointed the team somewhere.
        initial = getattr(self, "initial_data", None) or {}
        if "workflow" in initial:
            raise serializers.ValidationError(
                {
                    "workflow": (
                        "Routing is a decision of its own. Create the workflow "
                        "under this team, then point the team at it with the "
                        "route action."
                    )
                }
            )

        supplied = attrs.pop("new_workflow", None)
        if supplied is not None:
            self._new_workflow = supplied

        manager = attrs.pop("manager", None)
        if manager is not None:
            self._manager = manager

        campus = self._value(attrs, "campus")
        # A team being placed at a campus is an academic one unless HR says
        # otherwise. Campus has always been the marker of an academic team, so a
        # caller that sends a campus without naming a category is asking for
        # exactly that — not for an administration team that cannot have one.
        if "category" not in attrs and campus is not None and (
            self.instance is None
            or self.instance.category == Team.Category.ADMINISTRATION
        ):
            attrs["category"] = Team.Category.ACADEMIC
        category = attrs.get(
            "category",
            self.instance.category if self.instance is not None else Team.Category.ADMINISTRATION,
        )
        if campus is not None and not campus.is_active:
            raise serializers.ValidationError(
                {"campus": f'"{campus.name}" is retired. Choose an active campus.'}
            )
        # The category decides the campus relationship, so the pair is checked
        # here with the sentence that names the fix rather than left to a
        # database constraint that would only say the row is invalid.
        if category == Team.Category.ACADEMIC and campus is None:
            raise serializers.ValidationError(
                {
                    "campus": (
                        "An academic team sits at a campus — pick one, or "
                        "create it first. The campus is what makes campus-wide "
                        "approvers reachable for this team's stages."
                    )
                }
            )
        if category == Team.Category.ADMINISTRATION and campus is not None:
            raise serializers.ValidationError(
                {
                    "campus": (
                        "An administration team is not campus-based. Clear the "
                        "campus, or switch the category to Academic if this "
                        "team should sit at one."
                    )
                }
            )

        start = self._value(attrs, "effective_from")
        end = self._value(attrs, "effective_to")
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError(
                {
                    "effective_to": (
                        f"The end date ({end.isoformat()}) is before the start "
                        f"date ({start.isoformat()})."
                    )
                }
            )
        return attrs

    def get_is_team_manager(self, instance: Team) -> bool:
        """Whether the caller is the one manager this team was handed to.

        The roster and the default chain are the manager's to change, so the
        team screen reads this instead of re-deriving the rule from the viewer's
        role: HR sees the same roster read-only, and a manager sees their
        controls on their own team only.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return is_team_manager(user, instance)

    def get_workflows(self, instance: Team) -> list[dict]:
        """Every workflow this team owns, flagging the one it routes through.

        A team may hold several chains, so the team screen lists them rather
        than showing only the live one — otherwise a replacement HR is building
        would be invisible until somebody pointed the team at it.
        """
        return [
            {
                "id": workflow.pk,
                "name": workflow.name,
                "state": workflow.state,
                "is_active": workflow.is_active,
                "effective_from": workflow.effective_from,
                "is_routing": workflow.pk == instance.workflow_id,
                "section_count": workflow.sections.count(),
            }
            for workflow in instance.workflows.order_by("name")
        ]

    def get_members(self, instance: Team) -> list[dict]:
        """The people appointed on this team's chain, deduped across steps.

        A person may hold more than one step — the same role approving twice is
        legitimate — so the list is grouped by person with the steps and roles
        they serve in, rather than repeating them.
        """
        if instance.workflow_id is None:
            return []
        seen: dict[int, dict] = {}
        for section in instance.workflow.sections.order_by("order").select_related(
            "approver", "approver_role"
        ):
            if section.approver_id is None:
                continue
            user = section.approver
            entry = seen.setdefault(
                user.pk,
                {
                    "id": user.pk,
                    "user": user.pk,
                    "user_name": user.get_full_name() or user.username,
                    "user_email": user.email,
                    "sections": [],
                    "roles": [],
                },
            )
            entry["sections"].append(
                {"id": section.pk, "name": section.name, "order": section.order}
            )
            entry["roles"].append(
                {
                    "id": section.approver_role_id,
                    "label": section.approver_role.label,
                    "code": section.approver_role.code,
                }
            )
        return [seen[key] for key in sorted(seen)]

    def get_member_count(self, instance: Team) -> int:
        if instance.workflow_id is None:
            return 0
        return instance.workflow.sections.exclude(approver=None).count()

    def get_stage_roles(self, instance: Team) -> list[dict]:
        if instance.workflow_id is None:
            return []
        return [
            {"id": role.pk, "label": role.label, "code": role.code}
            for role in workflow_section_roles(instance.workflow)
        ]

    def get_sections(self, instance: Team) -> list[dict]:
        """The chain's steps, each with its one approver.

        A team screen has to show what the team routes through and who decides
        at each step, so the section summary is nested here rather than left to
        the caller to reassemble from a second request. A step with no approver
        reports ``approver: null`` rather than being omitted — an unstaffed step
        is the thing HR most needs to see on this screen.
        """
        if instance.workflow_id is None:
            return []
        return [
            {
                "id": section.pk,
                "name": section.name,
                "order": section.order,
                "is_active": section.is_active,
                "approver_role": section.approver_role.code,
                "approver_role_label": section.approver_role.label,
                "approver": (
                    {
                        "id": section.approver_id,
                        "user_name": section.approver.get_full_name()
                        or section.approver.username,
                        "user_email": section.approver.email,
                    }
                    if section.approver_id
                    else None
                ),
            }
            for section in instance.workflow.sections.order_by("order").select_related(
                "approver", "approver_role"
            )
        ]

    def create(self, validated_data: dict) -> Team:
        return create_team(
            actor=self.context["actor"],
            data=dict(validated_data),
            workflow_config=getattr(self, "_new_workflow", None),
            manager=getattr(self, "_manager", None),
        )

    def update(self, instance: Team, validated_data: dict) -> Team:
        return update_team(
            team=instance,
            actor=self.context["actor"],
            data=dict(validated_data),
            workflow_config=getattr(self, "_new_workflow", None),
            manager=getattr(self, "_manager", None),
        )


class TeamReadinessSerializer(serializers.Serializer):
    """The answer to "can this team route, and if not, why not?".

    Every problem is returned at once rather than the first one, because a
    configuration with three unstaffed steps should take HR one pass, not three.
    """

    team = serializers.CharField(source="team.name", read_only=True)
    status = serializers.CharField(source="team.status", read_only=True)
    ready = serializers.BooleanField(read_only=True)
    issues = serializers.SerializerMethodField()

    def get_issues(self, instance) -> list[dict]:
        return [
            {
                "code": issue.code,
                "field": issue.field,
                "message": issue.message,
                "section": issue.section,
                "approver_role": issue.approver_role,
            }
            for issue in instance.issues
        ]


class TeamMemberSummarySerializer(serializers.Serializer):
    """One employee on a team, with their workflow footprint for the roster."""

    id = serializers.IntegerField(read_only=True)
    user = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    designation = serializers.CharField(read_only=True)
    category = serializers.CharField(read_only=True)
    faculty = serializers.CharField(read_only=True)
    grade = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_section_approver = serializers.BooleanField(read_only=True)
    team_role = serializers.CharField(allow_null=True, read_only=True)
    workflow_memberships = serializers.ListField(read_only=True)
    workflow_count = serializers.IntegerField(read_only=True)


class TeamMemberAddSerializer(serializers.Serializer):
    """Place one employee on this team as a normal member."""

    user = serializers.IntegerField(
        min_value=1,
        help_text="The employee's user id. They must be active and have an employee record.",
    )

    def validate_user(self, value: int):
        user = User.objects.filter(pk=value).select_related(
            "employee_profile", "employee_profile__team"
        ).first()
        if user is None:
            raise serializers.ValidationError("That employee account is missing.")
        self.context["_resolved_user"] = user
        return value

    def create(self, validated_data: dict):
        user = self.context["_resolved_user"]
        return add_team_member(
            team=self.context["team"], user=user, actor=self.context["actor"]
        )



class TeamMemberBulkAddSerializer(serializers.Serializer):
    """Place several employees on this team in one all-or-nothing write.

    The picker sends the whole selection here so a single invalid employee
    cannot leave the roster with half of what was chosen. Refusals from the
    service arrive under ``users`` and name the people who could not join.
    """

    users = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        help_text="The user ids of the employees to place on this team.",
    )

    def validate_users(self, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Remove duplicate employees from the selection."
            )
        users = list(
            User.objects.filter(pk__in=value).select_related(
                "employee_profile", "employee_profile__team"
            )
        )
        by_id = {user.pk: user for user in users}
        missing = [str(user_id) for user_id in value if user_id not in by_id]
        if missing:
            raise serializers.ValidationError(
                "These employee accounts are missing: " + ", ".join(missing) + "."
            )
        self.context["_resolved_users"] = [by_id[user_id] for user_id in value]
        return value

    def create(self, validated_data: dict):
        return add_team_members(
            team=self.context["team"],
            users=self.context["_resolved_users"],
            actor=self.context["actor"],
        )
