"""Plain-data tracking contracts (Unit 15).

These dataclasses mirror the provisional tracking contract in the Unit 15
spec (section 1). They contain **no Django imports** so the provider interface
stays decoupled: the fixture provider (now) and the real provider (Unit 20)
both speak this shape, and the serializers translate it into the API response.

Unit 21 reconciled this contract with the real Unit 6/16 workflow model
(see ``workflows/docs/workflow-provider-contract.md``): the tracking provider
now serves real ``ApplicationStage``/``ApprovalDecision``/audit rows through
``DatabaseTrackingProvider``, and the frontend depends only on the serialized
shape, not on these classes.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TrackedApprover:
    """The approver resolved for an approval stage (nullable on a stage)."""

    name: str
    designation: str
    is_delegate: bool
    on_behalf_of: str | None


@dataclass(frozen=True)
class TrackedStage:
    """One stage of the workflow snapshot the application was submitted with.

    ``state`` is one of ``approved | awaiting | rejected |
    skipped | upcoming``. ``approver`` is ``None`` until the stage has been
    resolved to an approver. ``skip_reason`` carries why a skipped stage was
    passed over (Unit 30); it is ``None`` for every other state.
    """

    order: int
    role: str
    role_label: str
    state: str
    approver: TrackedApprover | None
    assigned_at: datetime | None
    decided_at: datetime | None
    comment: str | None
    skip_reason: str | None = None


@dataclass(frozen=True)
class TrackedEvent:
    """One entry in the activity history, newest first by contract."""

    id: str
    type: str
    occurred_at: datetime
    stage_order: int | None
    actor: dict
    comment: str | None
    resubmission_number: int | None


@dataclass(frozen=True)
class TrackedOutcome:
    """A rejection outcome attached to a terminal state.

    ``reason`` holds the mandatory rejection comment text; the serializer maps
    it to ``reason``.
    """

    stage_order: int
    role_label: str
    approver_name: str
    decided_at: datetime
    reason: str


@dataclass(frozen=True)
class ResubmissionInfo:
    """Resubmission state; the workflow track populates it in Unit 20."""

    count: int
    last_resubmitted_at: datetime | None
    can_resubmit: bool
    returns_to_stage: dict | None = None


@dataclass(frozen=True)
class WorkflowTracking:
    """The full workflow state for one application.

    ``status`` is one of ``pending | approved | rejected | cancelled``.
    ``stages`` are ascending by ``order``; ``events`` are newest first.
    ``rejection`` is non-null only while the application is rejected.
    """

    status: str
    approved_at: datetime | None
    current_stage: dict | None
    stages: tuple[TrackedStage, ...] = field(default_factory=tuple)
    events: tuple[TrackedEvent, ...] = field(default_factory=tuple)
    rejection: TrackedOutcome | None = None
    resubmission: ResubmissionInfo = field(
        default_factory=lambda: ResubmissionInfo(
            count=0, last_resubmitted_at=None, can_resubmit=False
        )
    )
    # Unit 18 additions: cancellation state appended to the same payload so
    # existing consumers keep working unchanged.
    cancelled_at: datetime | None = None
    cancellation_action: str | None = None
    cancellation_blocked_reason: str | None = None
    has_open_cancellation_request: bool = False
    latest_cancellation: dict | None = None