"""The default approver roles and approval-chain templates the product ships.

Roles are HR data, not migration seed (see migration 0028): a bare install starts
with none, and migration 0011's six canonical roles are removed once nothing
references them. This module is the product side of that decision — the one
place the *preset* content lives. It is applied on demand by HR through
:mod:`leave.services.setup`, never forced on every database by a migration.

This is deliberately the single source of truth for the six roles: the test
fixtures in :mod:`workflows.testing` import :data:`ROLE_SPECS` from here, so a
test can never pass against a role definition the product would not actually
create.
"""

from __future__ import annotations

from dataclasses import dataclass

from org.models import ApproverRole

#: The six canonical roles, with the behaviour each one carries. Mirrors what
#: migration 0011 used to seed, adapted to the current model: roles are HR data,
#: so this is what the preset offers — and what HR may edit afterwards.
ROLE_SPECS: dict[str, dict] = {
    "supervisor": {
        "label": "Supervisor",
        "description": "Line manager of the applicant.",
        "history_scope": ApproverRole.HistoryScope.ALL,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "hod": {
        "label": "Head of Department",
        "description": "Head of the applicant's team.",
        "history_scope": ApproverRole.HistoryScope.SAME_TEAM,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "dean": {
        "label": "Dean",
        "description": "Dean of the applicant's faculty.",
        "history_scope": ApproverRole.HistoryScope.SAME_FACULTY,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    "registrar": {
        "label": "Registrar",
        "description": "Institution-wide registrar; approves every application.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "campus_registrar": {
        "label": "Campus Registrar",
        "description": "Registrar for a single campus.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "dvc": {
        "label": "Deputy Vice-Chancellor",
        "description": "Deputy Vice-Chancellor; final institution-wide approval.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
}


@dataclass(frozen=True)
class WorkflowTemplate:
    """A ready-made approval chain HR can adopt for a team.

    ``sections`` is ordered and pairs the human step label with the approver
    role code the step names. The person who acts at each step is deliberately
    left to HR: a template describes the *shape* of a chain, not who currently
    occupies it, so a team built from one starts with unstaffed steps that
    activation refuses until they are filled.
    """

    key: str
    label: str
    description: str
    sections: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "sections": [
                {"name": name, "approver_role": code}
                for name, code in self.sections
            ],
        }


#: The two chains the university routes through, by employee category.
WORKFLOW_TEMPLATES: dict[str, WorkflowTemplate] = {
    "academic": WorkflowTemplate(
        key="academic",
        label="Academic",
        description=(
            "Supervisor → Head of Department → Registrar → "
            "Deputy Vice-Chancellor."
        ),
        sections=(
            ("Supervisor review", "supervisor"),
            ("Head of Department review", "hod"),
            ("Registrar review", "registrar"),
            ("Deputy Vice-Chancellor review", "dvc"),
        ),
    ),
    "administration": WorkflowTemplate(
        key="administration",
        label="Administration",
        description=(
            "Head of Department → Dean → Registrar → "
            "Deputy Vice-Chancellor."
        ),
        sections=(
            ("Head of Department review", "hod"),
            ("Dean review", "dean"),
            ("Registrar review", "registrar"),
            ("Deputy Vice-Chancellor review", "dvc"),
        ),
    ),
}


def workflow_template_config(key: str, team_name: str) -> dict:
    """The ``workflow_config`` a team created from ``key`` is written with.

    Shaped exactly as :func:`workflows.services.create_team` expects, so a team
    and its template chain land in one transaction. Every step's ``approver`` is
    ``None``: the template names roles, and HR appoints people afterwards (or
    the readiness check reports the gap and activation refuses).
    """
    template = WORKFLOW_TEMPLATES[key]
    return {
        "name": f"{team_name.strip()} workflow" if team_name.strip() else "Team workflow",
        "sections": [
            {"name": name, "approver_role": code, "approver": None}
            for name, code in template.sections
        ],
    }
