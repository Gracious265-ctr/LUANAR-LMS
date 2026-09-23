"""Application workflow assignment (Unit 16, section 3).

``assign_workflow`` is the only path that turns a submitted application into a
routed one: it resolves the application's stages through the swappable
``WorkflowProvider``, validates them (invariant 12.7), snapshots the
``ApplicationStage`` rows (invariant 12.5), and moves the application into the
``pending`` lifecycle state.

It runs in its own transaction; the Unit 14 submit service calls it inside its
own outer transaction so a bad workflow fails the whole submission cleanly.
"""

from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from leave.models import LeaveApplication

from .errors import WorkflowValidationError
from .models import STAGE_ROLE_CODES, ApplicationStage
from .providers import get_workflow_provider


def assign_workflow(application, *, actor=None):
    """Resolve, validate and snapshot the approval workflow for ``application``.

    Creates the ``ApplicationStage`` rows (first ``pending``, the rest
    ``waiting``, last one ``is_final``), sets ``application.current_stage`` and
    the responsible-approver spine, and moves the application to ``pending``.
    Idempotent: an application that already has stages is left untouched.

    Raises ``WorkflowValidationError`` when the provider returns no valid
    stage sequence with active approvers, so submission fails before any data
    is written.
    """
    with transaction.atomic():
        if application.current_stage is not None or (
            application.pk is not None
            and ApplicationStage.objects.filter(application_id=application.pk).exists()
        ):
            return application

        provider = get_workflow_provider()
        definitions = provider.get_stage_definitions(application)
        _validate_definitions(definitions)

        stages = []
        total = len(definitions)
        for definition in definitions:
            stages.append(
                ApplicationStage(
                    application=application,
                    stage_order=definition.order,
                    role=definition.role,
                    role_label=definition.role_label,
                    assigned_approver_id=definition.approver_user_id,
                    status=(
                        ApplicationStage.Status.PENDING
                        if definition.order == 1
                        else ApplicationStage.Status.WAITING
                    ),
                    is_final=definition.order == total,
                )
            )
        ApplicationStage.objects.bulk_create(stages)

        first_stage = stages[0]
        previous_status = application.status

        application.current_stage = first_stage
        application.current_approver_id = first_stage.assigned_approver_id
        application.status = LeaveApplication.Status.PENDING
        application.save(
            update_fields=["current_stage", "current_approver", "status"]
        )

        record_event(
            actor=actor or application.employee,
            action="leave_application.workflow_assigned",
            target=application,
            prev_state=previous_status,
            new_state=LeaveApplication.Status.PENDING,
            metadata={
                "reference_number": application.reference_number,
                "stages": [
                    {
                        "order": definition.order,
                        "role": definition.role,
                        "role_label": definition.role_label,
                    }
                    for definition in definitions
                ],
            },
        )
        return application


def _validate_definitions(definitions) -> None:
    if not definitions:
        raise WorkflowValidationError(
            "stages", "At least one approval stage is required."
        )

    orders = [definition.order for definition in definitions]
    if orders != list(range(1, len(definitions) + 1)):
        raise WorkflowValidationError(
            "stages", "Stage orders must be sequential starting from one."
        )
    if len(set(orders)) != len(orders):
        raise WorkflowValidationError(
            "stages", "Stage orders must be unique."
        )

    for definition in definitions:
        if definition.role not in STAGE_ROLE_CODES:
            raise WorkflowValidationError(
                "approver_role", "Select a valid approver role."
            )
        if not definition.approver_user_id:
            raise WorkflowValidationError(
                "stages",
                f"No active approver is available for the {definition.role_label} stage.",
            )