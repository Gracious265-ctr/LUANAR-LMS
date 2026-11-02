"""Approval-chain configuration and team serializers."""

from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.utils.text import slugify
from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave_types.models import LeaveType
from users.models import User

from campuses.models import Campus
from roles.models import ApproverRole
from teams.models import Team
from chains.models import Section, SectionMember, Workflow

from .models import WorkflowMember
from roles.services import (
    _resolve_stage_role,
    add_team_member,
    create_team_role_assignment,
    is_hr_actor,
    managed_team_ids_for,
)
from .providers import section_resolution
from .services import StageSequenceError, add_section_member, assign_workflow_member, create_team, create_workflow, normalize_section_sequence, remove_team_member, remove_workflow_member, sync_workflow_members, team_for_section, team_member_summaries, update_team, update_workflow, workflow_member_pool, workflow_section_roles

RESOLUTION_LABELS = {
    "section": "Set on this step",
    "team": "Team-wide approver",
    "campus": "Campus-wide approver",
    "institution": "Institution-wide approver",
    "unresolved": "Nobody can act here yet",
}


class ApproverRoleCodeField(serializers.Field):
    """An approver role addressed by its stable ``code``.

    Workflow payloads have always identified a stage's role by code
    (``"hod"``), and that stays the wire contract so saved forms and the HR
    picker keep working. The *storage* is now an ``ApproverRole`` row, so this
    field resolves the code to that row on the way in and echoes the code on the
    way out.

    An integer is accepted as a primary key too, which keeps ad-hoc API calls
    working, but code is the documented form.
    """

    default_error_messages = {
        "does_not_exist": "No approver role with code '{code}'.",
        "inactive": '"{label}" is deactivated. Reactivate it in Roles, or pick an active role.',
    }

    def to_representation(self, value: ApproverRole) -> str:
        return value.code

    def to_internal_value(self, data) -> ApproverRole:
        if isinstance(data, bool) or not isinstance(data, (str, int)):
            self.fail("does_not_exist", code=data)
        code = data
        if isinstance(data, int) or (isinstance(data, str) and data.isdigit()):
            role = ApproverRole.objects.filter(pk=int(data)).first()
        else:
            role = ApproverRole.objects.filter(code=str(data).strip()).first()
        if role is None:
            self.fail("does_not_exist", code=code)
        if not role.is_active:
            self.fail("inactive", label=role.label)
        return role


class SectionMemberSerializer(serializers.ModelSerializer):
    """One period during which a person can act for a section.

    The section is echoed with its name, order and role, not just its id: a
    membership row on its own says nothing about *which step of which workflow*
    the person is on, and the screens that list memberships show the step.

    The effective dates travel with the row because a membership is a period, not
    a flag: ``effective_to`` being set is how "no longer an approver" is
    recorded, and a reader that only saw the open rows could not tell an HR
    auditor who used to be on a step from somebody who was never on it.
    """

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    section_name = serializers.CharField(source="section.name", read_only=True)
    section_order = serializers.IntegerField(source="section.order", read_only=True)
    approver_role = serializers.CharField(
        source="section.approver_role.code", read_only=True
    )
    approver_role_label = serializers.CharField(
        source="section.approver_role.label", read_only=True
    )
    workflow = serializers.IntegerField(
        source="section.workflow_id", read_only=True
    )
    is_effective = serializers.SerializerMethodField()

    class Meta:
        model = SectionMember
        fields = [
            "id",
            "section",
            "section_name",
            "section_order",
            "workflow",
            "approver_role",
            "approver_role_label",
            "user",
            "user_name",
            "user_email",
            "effective_from",
            "effective_to",
            "is_effective",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "section_name",
            "section_order",
            "workflow",
            "approver_role",
            "approver_role_label",
            "user_name",
            "user_email",
            "is_effective",
            "created_at",
        ]

    def get_user_name(self, instance) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_user_email(self, instance) -> str:
        return instance.user.email

    def get_is_effective(self, instance) -> bool:
        """Whether this membership is in force today.

        Closed rows are served from ``all_objects`` so history is still
        readable; this flag is how a client tells the two apart without having to
        re-derive the date comparison.
        """
        return instance.is_effective()

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.get_user_name(instance)}"


class SectionSerializer(serializers.ModelSerializer):
    """One step in a workflow's approval sequence, and the person who decides it.

    ``approver_role`` is an :class:`ApproverRole` identified by its ``code``,
    with the label echoed alongside so a workflow is readable without a second
    lookup. ``approver`` is the single person the step routes to, writable
    through its primary key; ``approver_name`` is echoed for display. The
    effective-dated ``memberships`` are the record of who held the step and when,
    so "who approved this in March" stays answerable after the answer changes.
    """

    approver_role = ApproverRoleCodeField()
    approver_role_label = serializers.CharField(
        source="approver_role.label", read_only=True
    )
    approver = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text=(
            "The one person who approves this step. Must be a member of the "
            "owning team, and must already hold this step's role on that team."
        ),
    )
    approver_name = serializers.SerializerMethodField()
    resolution = serializers.SerializerMethodField()
    memberships = SectionMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "order",
            "approver_role",
            "approver_role_label",
            "approver",
            "approver_name",
            "resolution",
            "description",
            "is_active",
            "memberships",
        ]
        read_only_fields = [
            "id",
            "approver_role_label",
            "resolution",
            "memberships",
        ]

    def get_approver_name(self, instance) -> str | None:
        if instance.approver_id is None:
            return None
        return instance.approver.get_full_name() or instance.approver.username

    def get_resolution(self, instance) -> dict:
        """Where this step's approver comes from, and whether HR put it there.

        The workflow screen has to tell a **workflow-specific** approver —
        somebody appointed to this step by hand — apart from a **wide** one that
        resolves automatically (team, campus, institution), because they are
        configured in two different places and HR must not go looking for the
        wrong one when the holder changes.
        """
        source, user_id = section_resolution(instance)
        user_name = None
        if user_id is not None:
            user = User.objects.filter(pk=user_id).first()
            if user is not None:
                user_name = user.get_full_name() or user.username
        return {
            "source": source,
            "automatic": source in ("team", "campus", "institution"),
            "user": user_id,
            "user_name": user_name,
            "label": RESOLUTION_LABELS.get(source, source),
        }


class WorkflowSerializer(serializers.ModelSerializer):
    """A workflow, its owning team, and every stage it is made of.

    A workflow is readable on its own because HR configures one on its own: the
    workflow screen shows the stages, how each stage resolves its approver
    (set by hand, or automatically from a team/campus/institution-wide
    holding), who is a member of each, and the normal-member pool. Writing goes
    through :class:`WorkflowWriteSerializer`, which is where the team and the
    stage list are checked.
    """

    sections = SectionSerializer(many=True, read_only=True)
    state = serializers.CharField(read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    is_routing = serializers.SerializerMethodField()
    section_count = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "team",
            "team_name",
            "effective_from",
            "effective_to",
            "is_active",
            "state",
            "is_routing",
            "section_count",
            "sections",
            "members",
        ]
        read_only_fields = [
            "id",
            "effective_to",
            "state",
            "is_routing",
            "section_count",
            "sections",
        ]

    def get_is_routing(self, instance) -> bool:
        """True when this is the workflow the owning team actually routes."""
        team = instance.team
        return team is not None and team.workflow_id == instance.pk

    def get_section_count(self, instance) -> int:
        return instance.sections.count()

    def get_members(self, instance: Workflow) -> list[dict]:
        """The workflow's normal-member pool, with display names attached.

        Separate from ``sections``: section approvers decide each step; these
        are the team members on the chain who are not step appointments.

        Delegates to :class:`WorkflowMemberSerializer` rather than hand-rolling
        a shape: this payload feeds the chain's member roster, whose columns
        (name, designation, email) are exactly the fields that serializer owns.
        Two shapes for the same row is how a screen ends up counting three
        members and printing three blank names.
        """
        rows = (
            instance.workflow_members.select_related(
                "user", "user__employee_profile", "team", "workflow"
            )
            .order_by("user__first_name", "user__last_name", "user_id")
        )
        return WorkflowMemberSerializer(rows, many=True).data



class SectionMemberWriteSerializer(serializers.ModelSerializer):
    """Appoint one person as a section's approver.

    Separate from :class:`SectionMemberSerializer` (the nested read shape) so the
    nested workflow payload stays read-only: an appointment is made through this
    endpoint, which is where the actor and the audit entry are available.

    Writing the row also sets :attr:`Section.approver`, because the row and the
    appointment are one fact: the period is the record of who held the step, and
    ``approver`` is who holds it now. Letting them be written independently is
    how a step ends up with two answers.
    """

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = SectionMember
        fields = ["id", "section", "user", "effective_from", "created_at"]
        read_only_fields = ["created_at"]
        # Held to the same rule as role assignments: the service owns uniqueness
        # so the error can say who already holds the step.
        validators: list = []

    def validate_user(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                f"{value.get_full_name() or value.username} is not an active user. "
                "Activate the account before appointing them to a step."
            )
        return value

    def validate_section(self, value):
        """A manager staffs only a step of a team they run.

        The viewset scopes reads and lists to the teams the actor manages, but a
        write names its section directly, so the scope has to be re-asserted
        here or a manager could appoint somebody to *any* team's step by id. HR
        (and a superuser) keeps the whole institution.
        """
        actor = self.context.get("actor")
        if actor is None or is_hr_actor(actor):
            return value
        team = team_for_section(value)
        if team is None or team.id not in managed_team_ids_for(actor):
            raise serializers.ValidationError(
                "You may only appoint an approver to a step of a team you manage."
            )
        return value

    def create(self, validated_data: dict) -> SectionMember:
        return add_section_member(
            section=validated_data["section"],
            user=validated_data["user"],
            actor=self.context["actor"],
            effective_from=validated_data.get("effective_from"),
        )


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

    def get_workflows(self, instance: Team) -> list[dict]:
        """Every workflow this team owns, flagging the default one.

        A team may hold several chains, and it routes all of them at once for
        the people enrolled on each — ``is_routing`` names the default, not the
        only live chain. The screen lists every chain so an additional one is
        never mistaken for a chain that routes nothing.
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


class WorkflowMemberSerializer(serializers.ModelSerializer):
    """One normal member of a workflow, with the person and the owning team."""

    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = WorkflowMember
        fields = [
            "id",
            "workflow",
            "workflow_name",
            "user",
            "user_name",
            "user_email",
            "designation",
            "team",
            "team_name",
            "is_wide_approver",
            "added_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_name(self, instance) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_user_email(self, instance) -> str:
        return instance.user.email

    def get_designation(self, instance) -> str:
        profile = getattr(instance.user, "employee_profile", None)
        return getattr(profile, "designation", "") or ""


class WorkflowMemberWriteSerializer(serializers.Serializer):
    """Add one team member to a workflow's normal-member pool."""

    user = serializers.IntegerField(min_value=1)

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
        return assign_workflow_member(
            workflow=self.context["workflow"],
            user=user,
            actor=self.context["actor"],
            added_by=self.context["actor"],
        )


class WorkflowMemberPoolSerializer(serializers.Serializer):
    """The eligibility pool for a team's workflow memberships."""

    team = serializers.DictField(read_only=True)
    workflow = serializers.DictField(allow_null=True, read_only=True)
    available = serializers.ListField(read_only=True)
    current = serializers.ListField(read_only=True)
    assigned_elsewhere = serializers.ListField(read_only=True)
