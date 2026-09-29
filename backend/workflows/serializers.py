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
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    Workflow,
)
from .services import (
    ReassignmentError,
    StageSequenceError,
    _resolve_stage_role,
    _role_usage,
    acting_approver_identity,
    add_section_member,
    approver_role_codes_for,
    approver_role_labels_for,
    create_approver_role,
    create_campus,
    create_role_assignment,
    create_team,
    deactivate_approver_role,
    delegation_summary,
    is_approver_user,
    normalize_section_sequence,
    open_request_exists,
    reassign_application,
    role_usage_map,
    update_campus,
    update_approver_role,
    update_team,
    workflow_section_roles,
)


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
    """One step in a workflow's approval sequence, with its own approvers.

    ``approver_role`` is an :class:`ApproverRole` identified by its ``code``,
    with the label echoed alongside so a workflow is readable without a second
    lookup. ``members`` is the set of people who can act — the section is
    decided by whichever of them acts first.
    """

    approver_role = ApproverRoleCodeField()
    approver_role_label = serializers.CharField(
        source="approver_role.label", read_only=True
    )
    members = SectionMemberSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "order",
            "approver_role",
            "approver_role_label",
            "description",
            "is_active",
            "members",
            "member_count",
        ]
        read_only_fields = [
            "id",
            "approver_role_label",
            "members",
            "member_count",
        ]

    def get_member_count(self, instance) -> int:
        return instance.members.count()


class WorkflowSerializer(serializers.ModelSerializer):
    """Read-only view of a chain.

    A chain is written in the same request as the team that owns it — created
    with the team, and rewritten by saving the team again. This serializer
    exists so the team screens, the roster views, and the audit trail can read
    one, and it deliberately exposes no writable field: a chain has no edit of
    its own to offer, so the only way to change one is to name the team whose
    steps are changing.
    """

    sections = SectionSerializer(many=True, read_only=True)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "employee_category",
            "department",
            "effective_from",
            "is_active",
            "state",
            "sections",
        ]
        read_only_fields = fields


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
    """Create/update payload for a role; ``code`` is fixed by the seeds."""

    code = serializers.SlugField(max_length=50)
    label = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # Read-only on purpose. Retirement is the DELETE verb, which runs the
    # in-use guard; accepting is_active here would let a PATCH retire a role
    # that an active workflow, team, or holder still depends on.
    is_active = serializers.BooleanField(read_only=True)
    history_scope = serializers.ChoiceField(
        choices=ApproverRole.HistoryScope.choices, required=False
    )
    handles_cancellation = serializers.BooleanField(required=False, default=False)
    is_institution_wide = serializers.BooleanField(required=False, default=False)

    def validate_code(self, value: str) -> str:
        cleaned = slugify(value)
        if not cleaned:
            raise serializers.ValidationError(
                "The role code must be made of letters, numbers, or hyphens."
            )
        if cleaned != value:
            raise serializers.ValidationError(
                f'Use lowercase letters, numbers, and hyphens only, like "{cleaned}".'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """Reject a code that already exists, including a retired one.

        The unique index covers retired roles too, and that is deliberate:
        application stages snapshot the code, so reusing "dean" for a different
        purpose would rewrite the meaning of every historical decision. Catching
        it here turns what would otherwise be a database error into a message HR
        can act on.
        """
        if self.instance is not None:
            return attrs
        code = attrs.get("code")
        if code and ApproverRole.objects.filter(code=code).exists():
            raise serializers.ValidationError(
                {
                    "code": [
                        f'The code "{code}" is already used by another role. '
                        "Role codes appear in historical application stages, so "
                        "they cannot be reused, even after a role is retired."
                    ]
                }
            )
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
        role = attrs.get("role")
        if role is not None and not role.is_institution_wide:
            raise serializers.ValidationError(
                {
                    "role": f'"{role.label}" is a team role, not an '
                    "institution-wide role. Add this person to the team that "
                    "uses it instead."
                }
            )
        return attrs

    def create(self, validated_data: dict) -> RoleAssignment:
        return create_role_assignment(
            user=validated_data["user"],
            role=validated_data["role"],
            actor=self.context["actor"],
        )


class SectionMemberWriteSerializer(serializers.ModelSerializer):
    """Add or remove one person from one section.

    Separate from :class:`SectionMemberSerializer` (the nested read shape) so the
    nested workflow payload stays read-only: membership is changed through this
    endpoint, which is where the actor and the audit entry are available.
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
                "Activate the account before adding them to a section."
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

    A step names the role it needs and the people who may act for it. Naming both
    here is what lets a team be configured in one pass: HR is not asked to save
    a chain, go and look up its id, and paste it into a team form.
    """

    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    approver_role = serializers.CharField(max_length=100)
    order = serializers.IntegerField(required=False, min_value=1)
    members = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )

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
    # Read-only. A chain is not something a team points at; it is the chain that
    # was built with the team, and it is edited by writing its steps again. If
    # this were writable, a team's chain could be swapped for somebody else's
    # and every application inside it would be stranded at a step nobody staffs.
    workflow = serializers.PrimaryKeyRelatedField(read_only=True)
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
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
            "department",
            "campus",
            "campus_name",
            "workflow",
            "workflow_name",
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
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        supplied = attrs.pop("new_workflow", None)
        if self.instance is None and supplied is None:
            # A team with no chain routes nothing, and a team that exists
            # without one is the object that used to look configured and then
            # fail at submission.
            raise serializers.ValidationError(
                {
                    "new_workflow": (
                        "Describe the approval steps this team routes through. "
                        "The chain is created with the team."
                    )
                }
            )
        if supplied is not None:
            self._new_workflow = supplied

        department = attrs.get("department")
        if department is not None:
            attrs["department"] = department.strip()

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

    def get_members(self, instance: Team) -> list[dict]:
        if instance.workflow_id is None:
            return []
        seen: dict[int, dict] = {}
        for section in instance.workflow.sections.order_by("order").prefetch_related(
            "members__user"
        ):
            for membership in section.members.all():
                user = membership.user
                entry = seen.setdefault(
                    user.pk,
                    {
                        "id": None,
                        "user": user.pk,
                        "user_name": user.get_full_name() or user.username,
                        "user_email": user.email,
                        "sections": [],
                        "roles": [],
                    },
                )
                entry["id"] = membership.pk
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
        return (
            instance.workflow.sections.aggregate(n=Count("members"))["n"] or 0
        )

    def get_stage_roles(self, instance: Team) -> list[dict]:
        if instance.workflow_id is None:
            return []
        return [
            {"id": role.pk, "label": role.label, "code": role.code}
            for role in workflow_section_roles(instance.workflow)
        ]

    def get_sections(self, instance: Team) -> list[dict]:
        """The workflow's approval steps, with how many people may act at each.

        A team screen has to show the chain it routes through and who is
        available at each step, so the section summary is nested here rather
        than left to the caller to reassemble from a second request.
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
                "member_count": section.members.count(),
                # The same serializer the membership API uses, so a team screen
                # and the membership screen cannot disagree about a date.
                "members": SectionMemberSerializer(
                    section.members.select_related("user"), many=True
                ).data,
            }
            for section in instance.workflow.sections.order_by("order")
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
