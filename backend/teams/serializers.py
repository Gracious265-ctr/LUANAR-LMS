"""Team serializers: team CRUD, membership, readiness, and role holdings.

These were split out of ``workflows.serializers`` (and the team-wide holding out
of ``organisation.serializers``) so the ``teams`` app owns the whole Team feature
— its HTTP shapes included — rather than borrowing them from the apps it
happens to route through. The workflow-configuration serializers
(``WorkflowSerializer``, ``WorkflowWriteSerializer``, ``SectionMemberSerializer``)
stay in ``workflows``; the service functions they and these call still live in
``workflows.services`` and ``organisation.services``.
"""

from rest_framework import serializers

from users.models import User

from organisation.models import ApproverRole, Campus
from organisation.serializers import WideRoleAssignmentSerializer
from organisation.services import add_team_member, create_team_role_assignment
from teams.models import Team, TeamRoleAssignment
from workflows.models import Section
from workflows.services import create_team, update_team, workflow_section_roles


class TeamManagerInputSerializer(serializers.Serializer):
    """The team-wide role holding to designate as a team's manager.

    HR picks a team-scoped approver role and the person who holds it: the role is
    the capability the manager acts with, the person is who acts. Both are
    required — a manager without a role could not approve, and a role without a
    holder names nobody. The role/person/team rules (active, team-scoped, and
    category-matching) are enforced where every other wide holding is, in
    :func:`organisation.services.create_team_role_assignment`.
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
    # Every chain the team owns, listed rather than resolved to one: a team has
    # no single workflow of its own any more, because which chain an employee
    # follows is decided by their membership. The chain itself is built by the
    # manager through the workflow endpoints.
    workflows = serializers.SerializerMethodField()
    # The manager to designate, written on create (the second page of HR's
    # flow) or reassigned on update. A team is handed to a manager; the manager
    # then configures its chain and its members.
    manager = TeamManagerInputSerializer(write_only=True, required=False)
    # A team no longer holds members itself — its workflow's sections do. These
    # are flattened for display so the team list can show who is on the team
    # without a second request, but they are derived from the sections, so there
    # is exactly one place a person is recorded as able to act.
    members = serializers.SerializerMethodField()
    stage_roles = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()
    is_effective = serializers.BooleanField(read_only=True)

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
            "workflows",
            "manager",
            "status",
            "effective_from",
            "effective_to",
            "is_effective",
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "code",
            # Lifecycle is not editable here: activating and retiring go through
            # their own validated, audited actions rather than a PATCH, so
            # neither can happen by accident or without a validation record.
            "status",
            "is_effective",
            "workflows",
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        # Two fields HR used to write are now refused rather than ignored, so
        # an old client that still sends one learns the boundary instead of
        # believing it configured something. Chains are the manager's to build,
        # and an employee's chain is their own membership, not a setting on the
        # team.
        initial = getattr(self, "initial_data", None) or {}
        if "new_workflow" in initial:
            raise serializers.ValidationError(
                {
                    "new_workflow": (
                        "Approval chains are configured by the team's manager, "
                        "not by HR. Create the team, assign its manager, and "
                        "the manager builds the chain from their own portal."
                    )
                }
            )
        if "workflow" in initial:
            raise serializers.ValidationError(
                {
                    "workflow": (
                        "A team does not point at one chain. HR creates the team "
                        "and assigns its manager; the manager builds the chains "
                        "and puts each employee on the one they follow."
                    )
                }
            )

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

    def get_workflows(self, instance: Team) -> list[dict]:
        """Every workflow this team owns.

        All of them can be in force at once and each routes the employees who
        are members of it, so the team screen lists them all rather than naming
        one "live" chain — a replacement HR is building alongside the existing
        one is a real, routable chain the moment it is written, and hiding it
        behind a single headline would put that team's members out of view.
        """
        return [
            {
                "id": workflow.pk,
                "name": workflow.name,
                "state": workflow.state,
                "is_active": workflow.is_active,
                "effective_from": workflow.effective_from,
                "section_count": workflow.sections.count(),
            }
            for workflow in instance.workflows.order_by("name")
        ]

    @staticmethod
    def _sections_of(instance: Team):
        """Every step of every chain the team owns, chains in name order.

        One query rather than a loop over ``workflow.sections`` so a team that
        owns several chains still costs one round trip, and so the order the
        team screen shows steps in does not change when a second chain is
        added — a single-chain team reads exactly the list it read before.
        """
        return (
            Section.objects.filter(workflow__team=instance)
            .select_related("approver", "approver_role", "workflow")
            .order_by("workflow__name", "order")
        )

    def get_members(self, instance: Team) -> list[dict]:
        """The people appointed on this team's chain, deduped across steps.

        A person may hold more than one step — the same role approving twice is
        legitimate — so the list is grouped by person with the steps and roles
        they serve in, rather than repeating them.
        """
        if not instance.workflows.exists():
            return []
        seen: dict[int, dict] = {}
        for section in self._sections_of(instance):
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
        return Section.objects.filter(workflow__team=instance).exclude(
            approver=None
        ).count()

    def get_stage_roles(self, instance: Team) -> list[dict]:
        """The roles asked for across every chain, each once.

        The picker only needs to know which roles are in play; a role serving
        two of the team's chains is one role, not two entries, and the order
        stays first-seen so a single-chain team reads unchanged.
        """
        roles: list[ApproverRole] = []
        seen: set[int] = set()
        for workflow in instance.workflows.order_by("name"):
            for role in workflow_section_roles(workflow):
                if role.pk in seen:
                    continue
                seen.add(role.pk)
                roles.append(role)
        return [
            {"id": role.pk, "label": role.label, "code": role.code} for role in roles
        ]

    def get_sections(self, instance: Team) -> list[dict]:
        """The steps of every chain the team owns, each with its one approver.

        A team screen has to show what its employees are sent through and who
        decides at each step, so the section summary is nested here rather than
        left to the caller to reassemble from a second request — and because a
        team owns several chains, all of them are listed: an employee is inside
        one of them right now, so leaving one out is leaving a group of people
        off the screen. A step with no approver reports ``approver: null`` rather
        than being omitted — an unstaffed step is the thing HR most needs to see.

        ``workflow`` names the chain a step belongs to so steps from two chains
        (both of which start at 1) can be told apart.
        """
        return [
            {
                "id": section.pk,
                "workflow": section.workflow_id,
                "workflow_name": section.workflow.name,
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
            for section in self._sections_of(instance)
        ]

    def create(self, validated_data: dict) -> Team:
        return create_team(
            actor=self.context["actor"],
            data=dict(validated_data),
            manager=getattr(self, "_manager", None),
        )

    def update(self, instance: Team, validated_data: dict) -> Team:
        return update_team(
            team=instance,
            actor=self.context["actor"],
            data=dict(validated_data),
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


class WorkflowMemberPoolSerializer(serializers.Serializer):
    """The eligibility pool for a team's workflow memberships."""

    team = serializers.DictField(read_only=True)
    workflow = serializers.DictField(allow_null=True, read_only=True)
    available = serializers.ListField(read_only=True)
    current = serializers.ListField(read_only=True)
    assigned_elsewhere = serializers.ListField(read_only=True)


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
