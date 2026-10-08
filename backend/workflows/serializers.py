from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.utils.text import slugify
from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication, LeaveType
from users.models import User

from .models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    TeamRoleAssignment,
    Workflow,
    WorkflowMember,
)
from .providers import section_resolution
from .services import (
    ReassignmentError,
    StageSequenceError,
    WorkflowMemberError,
    _resolve_stage_role,
    _role_usage,
    acting_approver_identity,
    add_section_member,
    add_team_member,
    approver_role_codes_for,
    approver_role_labels_for,
    assign_workflow_member,
    create_approver_role,
    create_campus,
    create_campus_role_assignment,
    create_role_assignment,
    create_team,
    create_team_role_assignment,
    create_workflow,
    deactivate_approver_role,
    delegation_summary,
    is_approver_user,
    normalize_section_sequence,
    open_request_exists,
    reassign_application,
    remove_campus_role_assignment,
    remove_team_member,
    remove_team_role_assignment,
    remove_workflow_member,
    role_usage_map,
    sync_workflow_members,
    team_member_summaries,
    update_campus,
    update_approver_role,
    update_team,
    update_workflow,
    workflow_member_pool,
    workflow_section_roles,
)

RESOLUTION_LABELS = {
    "section": "Set on this step",
    "team": "Team-wide approver",
    "campus": "Campus-wide approver",
    "institution": "Institution-wide approver",
    "unresolved": "Nobody can act here yet",
}


def _record_delegation_created_audit(delegation: Delegation) -> None:
    """Audit a delegation request the moment it exists.

    The other three delegation actions are audited by
    ``workflows.services._record_delegation_audit``; creation is a serializer
    concern, so it is recorded here in the same transaction. Without it a
    request would appear in the trail only once HR decided on it, and a request
    that was never decided would leave no trace at all.
    """
    if delegation.requested_by_id is None:
        return
    record_audit(
        actor=delegation.requested_by,
        action=AuditEntry.Action.CREATED,
        target_type=AuditEntry.TargetType.DELEGATION,
        target_id=delegation.pk,
        target_summary=delegation_summary(delegation),
        detail=changed_fields(
            {},
            {
                "status": delegation.status,
                "delegate_id": delegation.delegate_id,
                "starts_on": delegation.starts_on,
                "ends_on": delegation.ends_on,
            },
        ),
        reason=delegation.request_reason,
    )


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
            "is_active",
            "state",
            "is_routing",
            "section_count",
            "sections",
            "members",
        ]
        read_only_fields = [
            "id",
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
        """
        rows = list(
            instance.workflow_members.select_related("user", "team").order_by(
                "user__first_name", "user__last_name", "user_id"
            )
        )
        return [
            {
                "id": row.user_id,
                "user": row.user_id,
                "full_name": row.user.get_full_name() or row.user.username,
                "email": row.user.email,
                "team": row.team_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]



class DelegationSerializer(serializers.ModelSerializer):
    """HR/approver-facing serializer for delegation requests."""

    approver = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )
    delegate = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    approver_name = serializers.SerializerMethodField()
    approver_role = serializers.SerializerMethodField()
    delegate_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Delegation
        fields = [
            "id",
            "approver",
            "approver_name",
            "approver_role",
            "delegate",
            "delegate_name",
            "starts_on",
            "ends_on",
            "request_reason",
            "requested_by",
            "requested_by_name",
            "decision_reason",
            "decided_by",
            "decided_at",
            "status",
            "state",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "requested_by",
            "decision_reason",
            "decided_by",
            "decided_at",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_approver_name(self, obj: Delegation) -> str:
        return obj.approver.get_full_name()

    def get_approver_role(self, obj: Delegation) -> str:
        """The approver's primary role code, from the role graph.

        ``User.role`` is only employee/approver/hr, so it cannot name the
        position somebody approves in. The first active holding supplies the
        label, falling back to the system role for HR and for a user whose
        holdings have all been removed.
        """
        codes = [
            code for code in approver_role_codes_for(obj.approver)
        ]
        if codes:
            return codes[0]
        return obj.approver.role

    def get_delegate_name(self, obj: Delegation) -> str:
        return obj.delegate.get_full_name() if obj.delegate else ""

    def get_requested_by_name(self, obj: Delegation) -> str:
        return obj.requested_by.get_full_name()

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_hr = getattr(user, "role", None) == User.Role.HR

        if is_hr:
            approver = attrs.get("approver")
            if approver is None:
                raise serializers.ValidationError(
                    {"approver": "Select the approver this delegation is for."}
                )
            if not is_approver_user(approver):
                raise serializers.ValidationError(
                    {"approver": "Select an active user with an approver role."}
                )
        else:
            approver = user
            attrs["approver"] = approver

        delegate = attrs.get("delegate")
        if delegate is not None:
            if not is_approver_user(delegate):
                raise serializers.ValidationError(
                    {"delegate": "Select an active user with an approver role."}
                )
            if delegate.pk == approver.pk:
                raise serializers.ValidationError(
                    {"delegate": "The delegate must be a different person from the approver."}
                )

        starts_on = attrs.get("starts_on")
        ends_on = attrs.get("ends_on")
        if starts_on is not None and ends_on is not None and ends_on < starts_on:
            raise serializers.ValidationError(
                {"ends_on": "End date must be on or after the start date."}
            )

        if approver is not None and open_request_exists(approver.pk):
            raise serializers.ValidationError(
                {"approver": "This approver already has an open delegation request."}
            )

        return attrs

    def create(self, validated_data: dict) -> Delegation:
        from notifications.delegations import DELEGATION_REQUESTED, notify_delegation

        request = self.context.get("request")
        validated_data["requested_by"] = getattr(request, "user", None)
        try:
            # The nested atomic block is a savepoint: a lost race against
            # ``one_open_request_per_approver`` rolls back cleanly instead of
            # poisoning the outer transaction, so the friendly 400 survives.
            with transaction.atomic():
                delegation = super().create(validated_data)
                _record_delegation_created_audit(delegation)
                notify_delegation(delegation.pk, DELEGATION_REQUESTED)
        except IntegrityError:
            raise serializers.ValidationError(
                {"approver": "This approver already has an open delegation request."}
            )
        return delegation


class DelegationActionSerializer(serializers.Serializer):
    """Payload for the HR approve / reject / cancel delegation actions."""

    decision_reason = serializers.CharField(required=False, allow_blank=True)
    delegate = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    def validate_decision_reason(self, value: str) -> str:
        return (value or "").strip()


class ReassignmentSerializer(serializers.ModelSerializer):
    """HR-facing serializer for emergency reassignment records."""

    application = serializers.PrimaryKeyRelatedField(
        queryset=LeaveApplication.objects.all()
    )
    to_approver = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    reference_number = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    from_approver = serializers.PrimaryKeyRelatedField(read_only=True)
    from_approver_name = serializers.SerializerMethodField()
    to_approver_name = serializers.SerializerMethodField()
    decided_by = serializers.PrimaryKeyRelatedField(read_only=True)
    decided_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Reassignment
        fields = [
            "id",
            "application",
            "reference_number",
            "employee",
            "employee_name",
            "from_approver",
            "from_approver_name",
            "to_approver",
            "to_approver_name",
            "reason",
            "decided_by",
            "decided_by_name",
            "created_at",
        ]
        read_only_fields = [
            "created_at",
        ]

    def get_reference_number(self, obj: Reassignment) -> str:
        return obj.application.reference_number or ""

    def get_employee(self, obj: Reassignment) -> int:
        return obj.application.employee_id

    def get_employee_name(self, obj: Reassignment) -> str:
        return obj.application.employee.get_full_name()

    def get_from_approver_name(self, obj: Reassignment) -> str:
        return obj.from_approver.get_full_name() if obj.from_approver else ""

    def get_to_approver_name(self, obj: Reassignment) -> str:
        return obj.to_approver.get_full_name()

    def get_decided_by_name(self, obj: Reassignment) -> str:
        return obj.decided_by.get_full_name()

    def validate_reason(self, value: str) -> str:
        return (value or "").strip()

    def create(self, validated_data: dict) -> Reassignment:
        request = self.context.get("request")
        try:
            return reassign_application(
                application=validated_data["application"],
                to_approver=validated_data["to_approver"],
                actor=getattr(request, "user", None),
                reason=validated_data.get("reason", ""),
            )
        except ReassignmentError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})


class PendingApplicationSerializer(serializers.Serializer):
    """Read-only representation of one pending (submitted) leave application.

    Reports both the *responsible* approver (the ``current_approver`` spine) and
    the *acting* approver (Unit 21 routing: the active delegate when one covers
    them). HR has to see the difference, because reassigning an application to
    an approver who is themselves away moves the spine without changing who
    actually acts — the queue would otherwise read as a successful intervention
    that quietly did nothing.
    """

    def to_representation(self, instance: LeaveApplication) -> dict:
        leave_type_name = ""
        if instance.leave_type_id:
            names = self.context.get("leave_type_names")
            if names is not None:
                leave_type_name = names.get(instance.leave_type_id, "")
            else:
                leave_type = LeaveType.objects.filter(
                    pk=instance.leave_type_id
                ).first()
                if leave_type is not None:
                    leave_type_name = leave_type.name
        current = instance.current_approver
        acting_id, acting_name = self._acting_approver(instance)
        if current is None:
            is_delegated = acting_id is not None
        else:
            is_delegated = acting_id is not None and acting_id != current.pk
        return {
            "id": instance.id,
            "reference_number": instance.reference_number or "",
            "employee": instance.employee_id,
            "employee_name": instance.employee.get_full_name(),
            "leave_type_name": leave_type_name,
            "start_date": instance.start_date,
            "end_date": instance.end_date,
            "calculated_days": instance.calculated_days,
            "reason": instance.reason,
            "submitted_at": instance.submitted_at,
            "current_approver": current.pk if current else None,
            "current_approver_name": current.get_full_name() if current else "",
            "acting_approver": acting_id,
            "acting_approver_name": acting_name,
            "is_delegated": is_delegated,
        }

    def _acting_approver(
        self, instance: LeaveApplication
    ) -> tuple[int | None, str]:
        """``(acting_approver_id, acting_approver_name)`` for one application.

        Prefers the page-level map the intervention queue resolves in bulk, so a
        whole page costs one delegation query plus one user query instead of two
        per row, and falls back to resolving this one application directly.
        """
        resolved = self.context.get("acting_approver_map")
        if resolved is not None and instance.pk in resolved:
            return resolved[instance.pk]
        return acting_approver_identity(instance)


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
    # Writable, and deliberately narrow: the workflow named has to be one this
    # team already owns (the service refuses anything else), so "route through
    # this chain instead" can never become "adopt somebody else's chain" — which
    # would strand every application inside the old one at a step nobody staffs.
    workflow = serializers.PrimaryKeyRelatedField(
        queryset=Workflow.objects.all(), required=False, allow_null=True
    )
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    workflows = serializers.SerializerMethodField()
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
        supplied = attrs.pop("new_workflow", None)
        if supplied is not None:
            self._new_workflow = supplied

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

        if "workflow" in attrs and self.instance is None and attrs["workflow"] is not None:
            raise serializers.ValidationError(
                {
                    "workflow": (
                        "A new team cannot adopt an existing workflow. Its "
                        "approval steps are written with it, or added "
                        "afterwards under the team."
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
        )

    def update(self, instance: Team, validated_data: dict) -> Team:
        return update_team(
            team=instance,
            actor=self.context["actor"],
            data=dict(validated_data),
            workflow_config=getattr(self, "_new_workflow", None),
        )


class TeamReadinessSerializer(serializers.Serializer):
    """The answer to "can this team be activated, and if not, why not?".

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
    """One team-wide holding: this role, on this team, held by this person."""

    class Meta:
        model = TeamRoleAssignment
        fields = [
            "id",
            "team",
            "role",
            "user",
            "user_name",
            "role_label",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
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
