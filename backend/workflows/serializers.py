from django.db import IntegrityError, transaction
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
    Team,
    TeamMember,
    Workflow,
    WorkflowStage,
)
from .services import (
    ReassignmentError,
    StageSequenceError,
    _role_usage,
    acting_approver_identity,
    add_team_member,
    create_campus,
    update_campus,
    approver_role_codes_for,
    approver_role_labels_for,
    role_usage_map,
    create_approver_role,
    create_role_assignment,
    create_team,
    deactivate_approver_role,
    delegation_summary,
    _resolve_stage_role,
    is_approver_user,
    normalize_stage_sequence,
    open_request_exists,
    reassign_application,
    team_stage_roles,
    update_approver_role,
    update_team,
    validate_workflow_for_activation,
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


class WorkflowStageSerializer(serializers.ModelSerializer):
    """One step in a workflow's approval sequence.

    ``approver_role`` is an :class:`ApproverRole` identified by its ``code``,
    with the label echoed alongside so a workflow is readable without a second
    lookup.
    """

    approver_role = ApproverRoleCodeField()
    approver_role_label = serializers.CharField(
        source="approver_role.label", read_only=True
    )

    class Meta:
        model = WorkflowStage
        fields = ["id", "order", "approver_role", "approver_role_label"]

    def validate_order(self, value: int) -> int:
        if value is None or value < 1:
            raise serializers.ValidationError(
                "Stage order must be a positive whole number."
            )
        return value


class WorkflowSerializer(AuditedModelSerializer):
    """HR-facing serializer for approval workflows and their ordered stages."""

    target_type = AuditEntry.TargetType.WORKFLOW

    stages = WorkflowStageSerializer(many=True)
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
            "stages",
        ]

    def _effective_is_active(self, attrs: dict) -> bool:
        if "is_active" in attrs:
            return bool(attrs["is_active"])
        if self.instance is not None:
            return bool(self.instance.is_active)
        return True

    def validate(self, attrs: dict) -> dict:
        name = self._value(attrs, "name")
        name = (name or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        category = self._value(attrs, "employee_category")
        attrs["employee_category"] = (category or "").strip()

        department = self._value(attrs, "department")
        attrs["department"] = (department or "").strip()

        stages = attrs.get("stages")
        if stages is None:
            raise serializers.ValidationError(
                {"stages": "Approval stages are required."}
            )
        try:
            normalized_stages = normalize_stage_sequence(stages)
        except StageSequenceError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})

        queryset = Workflow.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(name=name).exists():
            raise serializers.ValidationError(
                {"name": "A workflow with this name already exists."}
            )

        effective_from = self._value(attrs, "effective_from")
        if effective_from is not None and self._effective_is_active(attrs):
            self._validate_activation(
                normalized_stages,
                (attrs["employee_category"], attrs["department"]),
            )

        return attrs

    def _validate_activation(
        self, stages: list[dict], scope: tuple[str, str]
    ) -> None:
        workflow_pk = self.instance.pk if self.instance is not None else None
        issues = validate_workflow_for_activation(workflow_pk, scope, stages)
        if not issues:
            return
        field_errors: dict[str, list[str]] = {}
        details: list[str] = []
        for issue in issues:
            if issue.field is None:
                details.append(issue.message)
            else:
                field_errors.setdefault(issue.field, []).append(issue.message)
        errors: dict[str, object] = dict(field_errors)
        if details:
            errors["detail"] = " ".join(details)
        raise serializers.ValidationError(errors)

    def _audit_snapshot(self, instance: Workflow) -> dict:
        return {
            "name": instance.name,
            "employee_category": instance.employee_category,
            "department": instance.department,
            "effective_from": instance.effective_from,
            "is_active": instance.is_active,
            # Role *codes*, not ids, so the audit entry stays readable years
            # after the role is renamed or the row is hard to resolve.
            "stages": list(
                instance.stages.order_by("order").values_list(
                    "approver_role__code", flat=True
                )
            ),
        }

    def _audit_target_summary(self, instance: Workflow) -> str:
        scope = instance.employee_category or "All categories"
        if instance.department:
            scope += f" / {instance.department}"
        return f"{instance.name} ({scope})"

    def create(self, validated_data: dict) -> Workflow:
        stages = validated_data.pop("stages", [])
        with transaction.atomic():
            workflow = Workflow.objects.create(**validated_data)
            self._replace_stages(workflow, stages)
            self._audit_after_create(workflow)
        return workflow

    def update(self, instance, validated_data: dict) -> Workflow:
        stages = validated_data.pop("stages", [])
        before = self._audit_snapshot(instance)
        with transaction.atomic():
            # Bypass the automated audited update so the replacement stages are
            # in place before the "after" snapshot is taken.
            instance = serializers.ModelSerializer.update(self, instance, validated_data)
            self._replace_stages(instance, stages)
            self._audit_after_update(instance, before)
        return instance

    def _replace_stages(self, workflow: Workflow, stages: list[dict]) -> None:
        workflow.stages.all().delete()
        for stage in normalize_stage_sequence(stages):
            # The normalized payload carries a role *code*; the column is a FK,
            # so resolve it to the row before writing.
            role = _resolve_stage_role(stage["approver_role"])
            if role is None:
                raise serializers.ValidationError(
                    {
                        "approver_role": (
                            f"Approver role '{stage['approver_role']}' is missing "
                            "or deactivated."
                        )
                    }
                )
            WorkflowStage.objects.create(
                workflow=workflow, approver_role=role, order=stage["order"]
            )


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


class TeamMemberSerializer(serializers.ModelSerializer):
    """One person's role on one team."""

    # As with institution-wide holdings, inactive accounts reach
    # :func:`add_team_member` so the reason they cannot be staffed is explained.
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    # Code-keyed, like a workflow stage: HR staffs a team by naming the role,
    # not by looking up a primary key. Echoing the code keeps the payload in the
    # vocabulary the rest of the configuration API speaks.
    role = ApproverRoleCodeField()
    user_name = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = ["id", "team", "user", "user_name", "role", "role_label", "created_at"]
        read_only_fields = ["created_at"]
        # Declaring ``validators`` switches off the automatic
        # UniqueTogetherValidator. One member per role per team is enforced by
        # :func:`add_team_member` instead, which names the current holder —
        # "The fields team, role must make a unique set" is not an answer an HR
        # user can act on.
        validators: list = []

    def get_user_name(self, instance: TeamMember) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_role_label(self, instance: TeamMember) -> str:
        return instance.role.label

    def create(self, validated_data: dict) -> TeamMember:
        return add_team_member(
            team=validated_data["team"],
            user=validated_data["user"],
            role=validated_data["role"],
            actor=self.context["actor"],
        )


class TeamSerializer(serializers.ModelSerializer):
    """A team: the routing unit HR assigns people to."""

    campus = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    # Active chains only: a team pointing at a retired workflow routes nothing,
    # and the applicant would hit a configuration error at submission.
    workflow = serializers.PrimaryKeyRelatedField(
        queryset=Workflow.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    # Source is the real related name; without it DRF finds no attribute and
    # silently renders an empty list, which reads as "this team has no members".
    members = TeamMemberSerializer(many=True, read_only=True, source="memberships")
    stage_roles = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "code",
            "description",
            "campus",
            "campus_name",
            "workflow",
            "workflow_name",
            "is_active",
            "stage_roles",
            "member_count",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "code",
            "stage_roles",
            "member_count",
            "members",
            "created_at",
            "updated_at",
        ]

    def get_stage_roles(self, instance: Team) -> list[dict]:
        return [
            {"id": role.pk, "label": role.label, "code": role.code}
            for role in team_stage_roles(instance)
        ]

    def get_member_count(self, instance: Team) -> int:
        return instance.memberships.count()

    def create(self, validated_data: dict) -> Team:
        return create_team(actor=self.context["actor"], data=dict(validated_data))

    def update(self, instance: Team, validated_data: dict) -> Team:
        return update_team(
            team=instance, actor=self.context["actor"], data=dict(validated_data)
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
