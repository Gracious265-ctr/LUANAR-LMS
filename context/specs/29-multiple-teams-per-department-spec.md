# Unit 29 — One Department, Several Teams; One Chain Per Team

## The requirement

A department must be able to hold **one or more teams**, and **each team routes
through its own workflow**.

## What the code already gets right

Verified against the implementation on 2026-10-02, because most of the
requirement turns out to be standing already and the unit is smaller than it
looks:

| Requirement | Where it holds | Strength |
| --- | --- | --- |
| A department holds many teams | `Team.department` FK, `related_name="teams"` | Database-enforced one-to-many |
| A team has its own chain | `Team.workflow` is a `OneToOneField` | Database-enforced; a chain cannot be shared |
| A team cannot be pointed at another's chain | `TeamSerializer.workflow` is `read_only`; the only writer is the inline `new_workflow` | Enforced at the API |
| Routing follows the team | `DatabaseWorkflowProvider.get_stage_definitions` reads `team.workflow` | Enforced at the engine |
| One role per employee per department, across teams | `ensure_role_consistency` filters `workflow__team__department_id` | Correct across teams |

None of this needs changing. It is recorded here so the next reader does not
re-investigate it, and so the docstrings that describe it can be pointed at real
code.

## The defect

`workflows/services.py::_mismatched_department_team` made a second **active,
in-force** team in the same department an activation-blocking issue
(`department_conflict`).

That single check is the only thing preventing a department from holding several
active teams, and it contradicts four docstrings that all say the opposite:

- `Team`: "A `users.models.Department` holds **one or more** teams."
- `users.models.Department`: "A department, which holds one or more
  `workflows.Team` rows."
- `Team.department.help_text`: "A department holds one or more teams."
- `Department`'s own rules list: "one employee holds **one role across every team
  in the department**" — which presupposes more than one team per department.

The check's own docstring argues it is "nearly always accidental". That is a
product judgment, and the product has now made a different one. Worse, the
message it produced was self-defeating: *"If sharing it is intended, deactivate
that team first"* — so the only way to have two teams in a department was to make
one of them unable to route. A department could hold several team records and
never more than one working team, which is not what "one or more teams" means.

This is the Unit 28 defect class (§A "Promises the code does not keep") pointing
the other way: here the *documentation* is right and the code is wrong.

## Decisions

- **D1 — A department may hold any number of active teams.** `_mismatched_department_team`
  and the `department_conflict` issue are removed. Nothing replaces them: there is
  no ambiguity for a machine to resolve, because routing follows the team, and
  the team's own activation gate is unchanged.
- **D2 — `department_missing` stays.** It is not the same rule. A team with no
  department cannot be staffed at all, because the department is what scopes
  approvers. Removing the conflict check must not remove that one.
- **D3 — Routing is untouched, and now proven.** Nothing about per-team routing
  changes. But nothing tested it with two teams sharing a department, because that
  configuration was unreachable. The new tests submit through each of two teams in
  one department and assert each application is materialised with *its own* team's
  step — which is the actual proof of the second half of the requirement.
- **D4 — One role per employee per department is unchanged, and now proven across
  teams.** `ensure_role_consistency` already spans teams; with one team per
  department that path was never reachable. A test now appoints the same person as
  two different roles on two different teams of one department and expects the
  refusal.
- **D5 — Delete the superseded routing code.** `resolve_applicable_workflow` and
  its helper `_employee_key` resolve a chain by free-text `(category, department)`
  scope, the model that team routing replaced. Their own docstring says "retained
  for reference only ... and no longer calls this". They are reachable only from
  their own two tests. Dead code contradicting "routing follows the team" is the
  thing Unit 28 §B exists to remove, so it goes here rather than waiting.
- **D6 — Fix the docstrings that describe a section as a set of approvers.**
  `providers.py` and `assign_workflow` still say a section resolves to "a set of
  people" and that "a set of approvers per section" leaves nothing to skip. A
  section has exactly one approver now.

## Out of scope

- **Which team's chain an employee follows** — that is `EmployeeProfile`'s team
  assignment, unchanged.
- Anything about *which* teams exist, team naming, or department retirement.
- The hardening sweep in `28-hardening-and-integrity-review-spec.md`. D5 and D6
  are here only because this unit was already inside both files.

## Verification

1. `uv run manage.py test workflows leave --noinput` — the two apps that own
   this behaviour.
2. `uv run manage.py test --noinput` on a fresh database, count stated.
3. `manage.py check` and `makemigrations --check --dry-run` clean — this unit
   changes no schema.
4. No frontend change: the teams client renders
   `TeamReadiness.issues[].message` generically and never names
   `department_conflict`, so removing an issue code cannot strand the UI. Frontend
   suite still stated in the tracker.