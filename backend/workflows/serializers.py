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
    _role_usage,
    _resolve_stage_role,
    normalize_section_sequence,
    acting_approver_identity,
    add_section_member,
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
    normalize_section_sequence,
    open_request_exists,
    reassign_application,
    workflow_section_roles,
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


class SectionMemberSerializer(serializers.ModelSerializer):
    """One person who can act for a section.

    The section is echoed with its name, order and role, not just its id: a
    membership row on its own says nothing about *which step of which workflow*
    the person is on, and the screens that list memberships show the step.
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
            "created_at",
        ]

    def get_user_name(self, instance) -> str:
        return instance.user.get_full_name() or instance.user.username

    def get_user_email(self, instance) -> str:
        return instance.user.email

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


class WorkflowSerializer(AuditedModelSerializer):
    """HR-facing serializer for approval workflows and their ordered stages."""

    target_type = AuditEntry.TargetType.WORKFLOW

    sections = SectionSerializer(many=True)
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

        sections = attrs.get("sections")
        if sections is None:
            raise serializers.ValidationError(
                {"sections": "Approval sections are required."}
            )
        try:
            normalized_sections = normalize_section_sequence(sections)
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
                normalized_sections,
                (attrs["employee_category"], attrs["department"]),
            )

        return attrs

    def _validate_activation(
        self, sections: list[dict], scope: tuple[str, str]
    ) -> None:
        workflow_pk = self.instance.pk if self.instance is not None else None
        issues = validate_workflow_for_activation(workflow_pk, scope, sections)
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
            "sections": list(
                instance.sections.order_by("order").values_list(
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
        sections = validated_data.pop("sections", [])
        with transaction.atomic():
            workflow = Workflow.objects.create(**validated_data)
            self._replace_sections(workflow, sections)
            self._audit_after_create(workflow)
        return workflow

    def update(self, instance, validated_data: dict) -> Workflow:
        sections = validated_data.pop("sections", [])
        before = self._audit_snapshot(instance)
        with transaction.atomic():
            # Bypass the automated audited update so the replacement sections are
            # in place before the "after" snapshot is taken.
            instance = serializers.ModelSerializer.update(self, instance, validated_data)
            self._replace_sections(instance, sections)
            self._audit_after_update(instance, before)
        return instance

    def _replace_sections(self, workflow: Workflow, sections: list[dict]) -> None:
        """Rewrite the workflow's section sequence, preserving membership.

        A section is identified across writes by its ``(role, name)`` pair. A
        section whose pair still appears in the payload keeps its row, and so
        keeps its members: re-ordering the chain must not silently strip the
        people who can act for it, which is the whole reason a section holds
        several approvers.

        A section whose role **or** name changed is a different step and is
        rebuilt empty. Deliberately not carried over: a step that moved to a
        different approver role has a different authority, and quietly handing
        the old roster to the new role would grant it without HR asking. The
        step shows up with no members, which is visible and fixable, and
        submission is refused until it is staffed.

        ``(workflow, order)`` is unique, so the write is sequenced to avoid
        colliding with itself: stale sections go first, survivors are parked
        beyond any real order, and only then is the final order applied.
        """
        existing = list(
            workflow.sections.select_related("approver_role").prefetch_related("members")
        )
        by_identity = {(s.approver_role_id, s.name): s for s in existing}

        resolved: list[tuple[dict, ApproverRole]] = []
        for payload in normalize_section_sequence(sections):
            role = _resolve_stage_role(payload["approver_role"])
            if role is None:
                raise serializers.ValidationError(
                    {
                        "approver_role": (
                            f"Approver role '{payload['approver_role']}' is missing "
                            "or deactivated."
                        )
                    }
                )
            resolved.append((payload, role))

        # ``(payload, role, survivor_pk)``. A non-``None`` survivor keeps its row
        # and its members; ``None`` means build the step fresh.
        plan: list[tuple[dict, ApproverRole, int | None]] = []
        claimed: set[int] = set()
        for payload, role in resolved:
            survivor = by_identity.get((role.pk, payload["name"]))
            if survivor is not None and survivor.pk not in claimed:
                claimed.add(survivor.pk)
                plan.append((payload, role, survivor.pk))
            else:
                # Either a genuinely new step, or the same role+name a second
                # time in one payload — two steps may share a role and a label,
                # so the second needs its own row rather than reusing the first.
                plan.append((payload, role, None))

        # 1. Drop the steps that are no longer in the payload. Their members
        #    cascade. Doing this first means their orders are free for reuse.
        workflow.sections.exclude(pk__in=claimed).delete()

        # 2. Park the survivors, so writing the new order cannot collide with a
        #    surviving section that is currently sitting on the target order.
        for _, _, survivor_pk in plan:
            if survivor_pk is not None:
                Section.objects.filter(pk=survivor_pk).update(
                    order=F("order") + 1_000_000
                )

        # 3. Apply the final order, building the steps that have no row yet.
        for payload, role, survivor_pk in plan:
            if survivor_pk is not None:
                Section.objects.filter(pk=survivor_pk).update(
                    order=payload["order"]
                )
                continue
            Section.objects.create(
                workflow=workflow,
                name=payload["name"],
                approver_role=role,
                order=payload["order"],
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


class SectionMemberWriteSerializer(serializers.ModelSerializer):
    """Add or remove one person from one section.

    Separate from :class:`SectionMemberSerializer` (the nested read shape) so the
    nested workflow payload stays read-only: membership is changed through this
    endpoint, which is where the actor and the audit entry are available.
    """

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = SectionMember
        fields = ["id", "section", "user", "created_at"]
        read_only_fields = ["created_at"]
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
        required=True,
        allow_null=False,
        help_text=(
            "The approval workflow this team routes through. It owns the "
            "sections, so its steps define who may act for this team."
        ),
    )
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    # A team no longer holds members itself — its workflow's sections do. These
    # are flattened for display so the team list can show who is on the team
    # without a second request, but they are derived from the sections, so there
    # is exactly one place a person is recorded as able to act.
    members = serializers.SerializerMethodField()
    stage_roles = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()

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
            "sections",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "code",
            "stage_roles",
            "member_count",
            "members",
            "sections",
            "created_at",
            "updated_at",
        ]

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
            }
            for section in instance.workflow.sections.order_by("order")
        ]

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
