"""Plain-data tracking contracts (Unit 15).

These dataclasses mirror the provisional tracking contract in the Unit 15
spec (section 1). They contain **no Django imports** so the provider interface
stays decoupled: the fixture provider (now) and the real provider (Unit 20)
both speak this shape, and the serializers translate it into the API response.

Unit 20 must reconcile this contract with the real Unit 6 workflow model. The
frontend depends only on the serialized shape, not on these classes.
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

    ``state`` is one of ``approved | awaiting | rejected | returned |
    upcoming``. ``approver`` is ``None`` until the stage has been resolved to an
    approver.
    """

    order: int
    role: str
    role_label: str
    state: str
    approver: TrackedApprover | None
    assigned_at: datetime | None
    decided_at: datetime | None
    comment: str | None


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
    """A rejection or correction outcome attached to a terminal state.

    ``reason`` holds the mandatory reason/comment text; the serializer maps it
    to ``reason`` for rejections and ``comment`` for corrections.
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

    ``status`` is one of ``pending | approved | rejected |
    correction_required | cancelled``. ``stages`` are ascending by ``order``;
    ``events`` are newest first. ``rejection``/``correction`` are non-null only
    in their respective statuses and both reset to ``None`` once resubmitted.
    """

    status: str
    approved_at: datetime | None
    current_stage: dict | None
    stages: tuple[TrackedStage, ...] = field(default_factory=tuple)
    events: tuple[TrackedEvent, ...] = field(default_factory=tuple)
    rejection: TrackedOutcome | None = None
    correction: TrackedOutcome | None = None
    resubmission: ResubmissionInfo = field(
        default_factory=lambda: ResubmissionInfo(
            count=0, last_resubmitted_at=None, can_resubmit=False
        )
    )