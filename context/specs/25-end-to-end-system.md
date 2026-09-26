# Unit 25 — End-to-End System

> **DETAILED OUTLINE — expand to a full spec last.** Read `context/AGENTS.md` before implementation.
> The final integration/verification unit. Depends on Units 1–24. Does the complete-flow acceptance pass and produces the repeatable E2E verification the project lacks.

## Goal

Verify and finish the complete LUANAR leave-management workflow as one
integrated system: HR configuration → employee application → validation →
reference assignment → sequential approval through configured approvers →
final approval → annual-balance update → approved-document PDF generation →
notifications → employee/HR viewing, plus the rejection/correction/
resubmission/cancellation/delegation/reassignment branches. Deliver a
repeatable, scripted smoke test that anyone can run in dev to confirm the
whole chain works, and close the last integration gaps found.

## Design (to define in full spec)

- **Full flow to verify (from build plan):**
  1. HR creates employee, assigns grade, configures leave rules, configures workflow.
  2. Employee logs in, creates + submits an application; system validates, generates reference.
  3. Supervisor receives + approves; next configured approver receives; all mandatory stages approve.
  4. Final approver approves → annual balance updated → approved document generated (PDF) → emails sent.
  5. Employee views approved leave; HR sees finalized record.
  6. Branch checks: rejection, correction, resubmission, cancellation, delegation, reassignment all end-to-end.
- **Executable deliverable:** a dev seed script (`seed_e2e.py` or a management command) that provisions one complete HR config + workforce (grades, entitlements, leave types+rules, financial year, workflow, approvers with roles, an employee) and runs a deterministic scenario; plus the same as an automated integration test suite driving submit → sequential approve → final → balance → document → notifications → history. Where companies use seeders, this repo uses `leave/defaults.py::ensure_*` + the existing `seed_dev_users`/`seed_approvals_dev` — the E2E seed should compose them, not duplicate.
- **Packaging the check:** an `npm`-driven script (`frontend` `test:e2e` or a documented manual runbook) that (a) seeds the DB, (b) runs the backend flow tests, (c) checks the surface endpoints (dashboard `my/overview`, tracking, approvals, history, document content route), (d) confirms notification rows via the audit-capable API. Keep network-free (no external SMTP/Redis dependency; document-generation uses ReportLab locally + locmem/console email).
- **Only fix gaps this finds:** scope is bounded to defect fixes that break the verified chain, not feature expansion; anything new is filed as a follow-up in `progress-tracker.md`.

## Implementation (to expand)

1. `seed_e2e` management command composing `leave/defaults.py` + approver/user seeds into one reproducible scenario.
2. E2E test module (`backend` integration tests via `manage.py test`, marked to run serially with a dedicated `TEST_DB_NAME`): happy-path full chain + the six branch flows; assert balance ledger rows, PDF existence content, `Notification` rows, `AuditEvent` trail.
3. Frontend E2E/runbook: script + manual checklist across dashboard → form → submit → tracking → approval → final → document → history, verifying each visible result.
4. Fix-integration gaps surfaced by the run (documented in `troubleshooting-notes.md`).
5. Update `README.md` quickstart with the one-command verification; final reconciliation of `progress-tracker.md` (mark Units 20–25 complete).

## Dependencies

- Existing packages only (ReportLab from Unit 23); no new dependencies expected. Reuses all prior units; the HR audit/dashboard from Units 11/12 (absorbed into 24) is part of the verified surface.

## Verification checklist (to expand)

- `note`: the E2E happy path passes from a clean seed.
- All six branch flows pass.
- Backend full suite + frontend `npm test`/`tsc`/`eslint`/`build` green.
- README one-command verification documented and runnable.