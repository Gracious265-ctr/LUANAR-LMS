"""Which of a team's chains a person's applications route through.

A team routes **one or more chains at the same time**. It may own several
:class:`~chains.models.Workflow` rows, and the people on it are enrolled on them
one at a time (:class:`~chains.models.WorkflowMember`) — the same enrolment that
decides eligibility, so a team that builds a second chain is not a team that
switches chains.

That makes "which chain do I route through" a per-person question, and this
module is the single answer to it. The team's people are enrolled on its chains
one at a time, and each person's leave routes through the chain they are
enrolled on (if any). Two people on one team can therefore route in parallel,
through different chains, at the same moment.

The resolver is shared deliberately: the submission path materialises the chain
it names, and the "On Leave" read scope treats the people it names as the
viewer's chain. Two implementations of "my chain" would sooner or later show a
team member a colleague whose leave routes somewhere else.
"""

from __future__ import annotations

from teams.models import Team
from users.models import EmployeeProfile

from .models import Workflow, WorkflowMember


def _pick_chain(chain_ids: list[int]) -> int | None:
    """The chain a person routes through, given the chains they are enrolled on.

    Enrolment wins, because it is the explicit statement of which of the
    team's chains this person belongs to. A person is a normal member of one
    workflow, so this normally sees a single id; the lowest-id tie-break stays
    as a defensive rule for rows written before that constraint.
    """
    ordered = sorted({chain_id for chain_id in chain_ids if chain_id is not None})
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    return ordered[0]


def routed_workflow_for(team: Team | None, user=None) -> Workflow | None:
    """The chain ``team`` routes ``user``'s applications through, or ``None``.

    ``user`` may be a loaded :class:`~users.models.User` or a bare user id.
    ``None`` comes back when the team has no default chain and the person is
    enrolled on none — the caller reports that as a configuration problem naming
    the team.

    Since a team routes all its chains (enrolled people and nothing else),
    there is no "default fallback" — if the person has no enrolment and no
    default chain, the answer is ``None`` and the caller reports a problem.
    """
    if team is None:
        return None
    user_id = user.pk if hasattr(user, "pk") else user
    if user_id is None:
        return None

    enrolled = WorkflowMember.objects.filter(team=team, user_id=user_id).values_list(
        "workflow_id", flat=True
    )
    chain_id = _pick_chain(list(enrolled))
    if chain_id is None:
        return None
    return Workflow.objects.filter(pk=chain_id).first()


def routed_workflow_for_user(user) -> Workflow | None:
    """The chain the signed-in person's own leave routes through, if any.

    Since a team routes all its chains, there is no "default fallback": the
    person must be enrolled on a chain for it to be their routing chain.
    """
    if user is None:
        return None
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        profile = (
            EmployeeProfile.objects.filter(user=user)
            .select_related("team")
            .first()
        )
    if profile is None or profile.team_id is None:
        return None
    return routed_workflow_for(profile.team, user)


def routed_chain_ids_by_user(team: Team | None) -> dict[int, int]:
    """Every person on ``team`` and the chain their leave routes through.

    The bulk sibling of :func:`routed_workflow_for`, for the reads that ask the
    question about a whole team: it reads the team's enrolments and roster once
    and applies the same rule in memory, so a list screen costs a fixed number
    of queries rather than one per person. People with no chain at all are
    absent from the answer.
    """
    if team is None:
        return {}
    enrolled: dict[int, list[int]] = {}
    for user_id, workflow_id in WorkflowMember.objects.filter(team=team).values_list(
        "user_id", "workflow_id"
    ):
        enrolled.setdefault(user_id, []).append(workflow_id)

    roster = set(
        EmployeeProfile.objects.filter(team=team).values_list("user_id", flat=True)
    )
    routed: dict[int, int] = {}
    for user_id in roster | set(enrolled):
        chain_id = _pick_chain(enrolled.get(user_id, []))
        if chain_id is not None:
            routed[user_id] = chain_id
    return routed
