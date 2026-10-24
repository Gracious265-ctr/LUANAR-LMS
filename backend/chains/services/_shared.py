"""Shared vocabulary for the workflow service package.

Errors, result dataclasses, and the small helpers that more than one submodule
needs. Everything here is imported *by* the submodules rather than re-exported
alone, so the error types a caller catches are the same objects whichever path
raised them.
"""

from dataclasses import dataclass

from django.utils.text import slugify

from audit.services import changed_fields, record_audit
from roles.services import is_hr_actor, is_team_manager
from teams.models import Team
from chains.models import Workflow

__all__ = [
    "StageSequenceError",
    "TeamActionError",
    "TeamIssue",
    "TeamReadiness",
    "WorkflowActionError",
    "WorkflowAssignmentError",
    "_require_can_manage_team",
    "_unique_team_code",
    "_unique_workflow_name",
    "changed_fields",
    "record_audit",
]


class WorkflowAssignmentError(Exception):
    """The application could not be assigned a workflow; carries messages."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


class StageSequenceError(ValueError):
    """Raised when a submitted workflow stage list is invalid.

    ``field`` is the API field the error belongs to; ``index`` is the 0-based
    stage position when the error is specific to one stage.
    """

    def __init__(self, field: str, message: str, index: int | None = None):
        super().__init__(message)
        self.field = field
        self.message = message
        self.index = index


class TeamActionError(ValueError):
    """Raised when a team or team-member write cannot be applied.

    ``field`` is the API field the error belongs to. ``issues`` carries the
    structured :class:`TeamIssue` list when the refusal came from validating a
    whole configuration (activation), so a client can render each problem
    against the step that caused it instead of parsing one long sentence.
    """

    def __init__(
        self,
        field: str,
        message: str,
        issues: tuple["TeamIssue", ...] | list["TeamIssue"] | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.message = message
        self.issues = tuple(issues or ())


class WorkflowActionError(ValueError):
    """Raised when a workflow write cannot be applied.

    ``field`` is the API field the error belongs to.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class TeamIssue:
    """One reason a team is not ready to route applications.

    ``code`` is stable and machine-readable so a client can react to a specific
    problem rather than parsing the sentence; ``field`` is the API field the
    issue belongs to, so a form can put it next to the input that caused it.
    ``section`` is the 1-based approval order when the issue is about one step.
    """

    code: str
    field: str
    message: str
    section: int | None = None
    approver_role: str = ""


@dataclass(frozen=True)
class TeamReadiness:
    """The outcome of checking a team, and whether it may be activated.

    ``ready`` is False when *any* issue was found: a team is only ever
    all-or-nothing, because a chain with one unstaffed step strands every
    application that reaches it and the employee finds out at the worst
    possible moment. The issues are returned whole rather than the first
    failure so HR can fix the configuration in one pass.
    """

    team: Team
    issues: tuple[TeamIssue, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "issues": [
                {
                    "code": issue.code,
                    "field": issue.field,
                    "message": issue.message,
                    "section": issue.section,
                    "approver_role": issue.approver_role,
                }
                for issue in self.issues
            ],
        }


def _require_can_manage_team(actor, team, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR or ``team``'s designated manager.

    A team's day-to-day configuration belongs to its manager once HR has handed
    the team over, but HR keeps the same reach so an installation that has not
    yet designated a manager is not locked out of its own teams. ``error_cls``
    lets each family of operations raise the error its caller already
    translates.
    """
    if is_hr_actor(actor) or is_team_manager(actor, team):
        return
    raise error_cls(
        "detail", "You do not have permission to manage this team."
    )


def _unique_team_code(name: str) -> str:
    """Derive a unique slug code from a team name.

    HR names a team; the code is machine-facing (it is what other systems and
    reports key off), so it is derived rather than typed. Two different names
    can slug to the same thing — "R & D" and "R&D" both give "r-d" — so the
    suffix loop keeps creation from failing on the unique index.
    """
    base = slugify(name)[:40] or "team"
    candidate = base
    suffix = 2
    while Team.objects.filter(code=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique_workflow_name(base: str, exclude_pk: int | None = None) -> str:
    """A unique workflow name derived from the team being created or edited.

    ``exclude_pk`` is the workflow being renamed, which does not count as a
    clash with itself — otherwise saving a team without touching the chain name
    would rename it to "… (2)" every time.
    """
    base = (base or "").strip() or "Team workflow"
    candidate = base
    suffix = 2
    while (
        Workflow.objects.filter(name=candidate)
        .exclude(pk=exclude_pk)
        .exists()
    ):
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate
