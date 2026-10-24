"""Chain materialisation: turning a configured workflow into a live stage chain.

When an application is submitted, the workflow provider's section definitions are
validated and written out as :class:`~approvals.models.ApplicationStage` rows,
with the eligibility of each section snapshotted at that moment. The snapshot is
what makes an in-flight application immune to later membership edits (invariant
12.5) and what self-approval is enforced through.

The chain always starts at section one and no mandatory section is ever skipped;
the provider decides the shape, including the stages a *skipped* stage records,
and this module only materialises it.
"""

from django.db import transaction

from approvals.models import ApplicationStage, ApplicationStageApprover
from audit.models import AuditEntry
from audit.services import record_audit
from chains.services import WorkflowAssignmentError


def assign_workflow(application):
    """Materialise the configured section chain for ``application``.

    Runs idempotently: if the current submission cycle already has stages, the
    existing live stage is returned unchanged. Otherwise the workflow provider's
    section definitions are validated and bulk-created with exactly one ``pending``
    stage, and ``application.current_stage`` is pointed at it.

    **The chain always starts at section one, and no section is ever skipped.**
    A step names one person, and if that person is the applicant they cannot act
    on their own leave, so the provider refuses to resolve the step at all and
    submission is refused there rather than routing the application past a step
    (invariants 12.3, 12.7). The old "start after the applicant's last stage,
    never travelling backwards" rule is gone with the multi-approver sections it
    existed for: there is nothing to skip, because there is nothing else in a
    step.

    Raises :class:`WorkflowAssignmentError` when the provider yields no/ill-formed
    sections or a section cannot be resolved to at least one active user other
    than the applicant.
    Returns the first (pending) stage.
    """
    from chains.providers import WorkflowConfigError, get_workflow_provider

    with transaction.atomic():
        cycle = application.submission_cycle
        existing = application.stages.filter(submission_cycle=cycle).first()
        if existing is not None:
            return application.current_stage

        try:
            definitions = get_workflow_provider().get_stage_definitions(application)
        except WorkflowConfigError as exc:
            raise WorkflowAssignmentError([str(exc)])
        if not definitions:
            raise WorkflowAssignmentError(["No workflow sections configured."])
        orders = [definition.order for definition in definitions]
        if sorted(orders) != list(range(1, len(definitions) + 1)):
            raise WorkflowAssignmentError(
                ["Workflow sections must be ordered 1..N."]
            )
        # A section nobody can act for is refused here rather than materialised
        # and left pending forever. The provider normally raises for this, but
        # assign_workflow is also reachable with a provider that returns a gap,
        # and an eligibility row cannot name nobody.
        unstaffed = [
            f'No active approver for the "{definition.role_label}" approval section.'
            for definition in definitions
            if not definition.approver_user_ids and not definition.skipped
        ]
        if unstaffed:
            raise WorkflowAssignmentError(unstaffed)

        # Every routable definition carries at least one eligible user: the
        # provider refuses an unsatisfiable section rather than returning a gap,
        # and it has already removed the applicant. A *skipped* definition
        # deliberately carries none -- nobody may act there -- so it is exempt
        # from the check above (Unit 30).
        #
        # The chain's shape is therefore decided by the provider, not here. It
        # starts at section one for an ordinary applicant, at the first stage
        # above the applicant's own for an approver applicant, and at an appended
        # HR stage when the applicant holds the final step.
        last_index = len(definitions) - 1
        # The one stage that opens pending: the lowest order the provider did not
        # skip. Every provider must leave at least one routable stage, or there
        # is nothing to decide -- the HR destination is what stops that happening
        # when the applicant holds the final step.
        pending_order = min(
            (d.order for d in definitions if not d.skipped),
            default=None,
        )
        if pending_order is None:
            raise WorkflowAssignmentError(
                ["This workflow has no approval stage left for HR to decide."]
            )
        stages = [
            ApplicationStage(
                application=application,
                submission_cycle=cycle,
                stage_order=definition.order,
                role=definition.role,
                role_label=definition.role_label,
                role_ref_id=definition.role_id,
                history_scope=definition.history_scope or "",
                handles_cancellation=definition.handles_cancellation,
                section_ref_id=definition.section_id,
                assigned_approver=None,
                status=_initial_stage_status(definition, pending_order),
                skip_reason=definition.skip_reason,
                is_final=index == last_index,
            )
            for index, definition in enumerate(definitions)
        ]

        ApplicationStage.objects.bulk_create(stages)

        # Snapshot who may act on each section, now. This is what makes an
        # in-flight application immune to later membership edits (invariant
        # 12.5) and what self-approval is enforced through.
        ApplicationStageApprover.objects.bulk_create(
            ApplicationStageApprover(stage=stage, user_id=user_id)
            for stage, definition in zip(stages, definitions)
            for user_id in definition.approver_user_ids
        )

        # The application opens at the stage that was materialised pending, not
        # at the first stage in the chain: a chain that starts with skipped stages
        # has to point at the one somebody can act on (Unit 30).
        opening = next(
            stage
            for stage in stages
            if stage.status == ApplicationStage.Status.PENDING
        )
        application.current_stage = opening
        application.current_approver = None
        application.save(update_fields=["current_stage", "current_approver", "updated_at"])
        _record_skipped_stages(application, stages)
        notify_stage_pending(opening, application)
        return opening


def _record_skipped_stages(application, stages) -> None:
    """Audit the stages an application was not routed through (Unit 30).

    Written by the applicant, because the applicant is who caused it: their own
    position decided the chain. Without this the audit trail would show a chain
    starting at stage two with nothing saying why, which is the one question an
    audit exists to answer.
    """
    skipped = [
        {
            "order": stage.stage_order,
            "role_label": stage.role_label,
            "reason": stage.skip_reason,
        }
        for stage in stages
        if stage.status == ApplicationStage.Status.SKIPPED
    ]
    if not skipped:
        return
    orders = ", ".join(str(entry["order"]) for entry in skipped)
    record_audit(
        actor=application.employee,
        action=AuditEntry.Action.STAGE_SKIPPED,
        target_type=AuditEntry.TargetType.APPLICATION,
        target_id=application.pk,
        target_summary=(
            f"{application.reference_number}: stage(s) {orders} skipped"
        ),
        detail={
            "stages": skipped,
            "reason": "The applicant's own position is at or below this stage.",
        },
    )


def notify_stage_pending(stage, application) -> None:
    """Tell everyone entitled to act that this stage is now open (unit 08 §2.1).

    A stage is never assigned to one person — the section resolves by whoever
    acts first — so each snapshotted eligible approver gets the one feed row.
    Written inside the caller's transaction: the notification is part of the
    same business event as the stage opening, so it commits or rolls back with
    it.
    """
    from notifications.services import create_notification

    for approver in stage.eligible_approvers.select_related("user"):
        create_notification(
            recipient=approver.user,
            event_type="approval.assigned",
            message=(
                f"A leave application needs your review: "
                f"{application.reference_number}"
            ),
            link=f"/dashboard/approvals/{application.pk}",
        )


def _initial_stage_status(definition, pending_order: int) -> str:
    """The status a freshly materialised stage starts in.

    Driven by the definition rather than by its position (Unit 30). The provider
    decides which stage the application actually opens at:

    * a **skipped** stage is born ``SKIPPED`` -- terminal, carrying the reason the
      provider recorded. It is never pending, so it never reaches an approver's
      queue and never raises a notification;
    * the first stage the provider did not skip is ``PENDING`` and the rest are
      ``WAITING``. For an ordinary applicant that is section one; for an approver
      applicant it is the first stage above their own.
    """
    if definition.skipped:
        return ApplicationStage.Status.SKIPPED
    if definition.order == pending_order:
        return ApplicationStage.Status.PENDING
    return ApplicationStage.Status.WAITING
