# Unit 28 — Hardening and Integrity Review

## Why this unit exists

The build plan is exhausted: Units 1–26 are implemented, verified and committed,
and the next piece of work is a planning decision rather than a queued unit. That
makes this the point at which a review pass over the whole track earns its cost
(`progress-tracker.md`, "Next Up", candidate 3).

It is also not optional tidying. On 2026-10-02 a verification pass found that
**four backend tests had been failing since `8d472b3`** and that every
verification claim in `context/progress-tracker.md` predated that commit. Four
consecutive commits were recorded as verified. The suite was not the gate it was
believed to be.

The failure had one cause worth naming, because it recurs: **the code claimed
behaviour it did not have, and the documentation agreed with the claim rather
than the code.** A comment said every employee edit bumps `row_version` so a
stale tab is rejected; nothing bumped it and nothing read it. A test relied on a
fixture-registry fallback that a commit had deliberately removed. `architecture.md`
described a section as holding several approvers three commits after the model
was changed to hold exactly one.

This unit looks for that class of defect, because it is the class that survives
review.

## Scope

The unit is a **review with fixes**, not a rewrite. Nothing here may change
business behaviour that a specification or an approved decision already fixes; the
pass corrects what the code and docs claim against what they do.

### A. Promises the code does not keep

Every comment, docstring, `help_text`, invariant in `architecture.md`, and
`README.md` claim that names a behaviour, checked against the implementation.
The three found so far are fixed (below); this is the sweep for the rest.

Highest-risk locations, because that is where the claims were:

- `architecture.md` §12 — the invariants. Each one should be traceable to the
  code that enforces it.
- Model `help_text` and docstrings on `Section`, `Team`, `SectionMember`,
  `LeaveApplication`, `CancellationRequest`, `ApprovedLeaveDocument`.
- `README.md` — the API table, verified endpoint by endpoint against
  `config/urls.py` and each viewset's `http_method_names`.

### B. Dead code and dead schema

Anything declared and never read, written, or imported.

- Already removed: `LeaveApplication.row_version` (`leave/0017`),
  `leave/services/snapshots.py`.
- The remaining surface to sweep: unused model fields, unused serializer fields,
  unreferenced frontend modules, and `lib/` fixture files with no consumer.

### C. Frontend/backend contract

Per endpoint the frontend calls: the route exists, the method is allowed, and the
payload the browser sends matches what the serializer accepts. `apiFetch` handles
refresh-and-retry centrally, so the pass starts from every call site in
`frontend/lib/**-client.ts`, `lib/*/service.ts` and `frontend/app/api/**`.

Two contract questions already answered during the scoping of this unit, recorded
so they are not re-opened:

- The edit/resubmit path is **sound**. `LeaveApplicationSerializer` marks
  `working_days`, `calendar_days`, `calculated_days` and `financial_year_label`
  read-only, so the server computes them and a browser cannot set them.
- `WorkflowViewSet` is **correctly** read-only
  (`http_method_names = ["get", "head", "options"]`). `README.md` is what is wrong
  — it documents a `POST` and a `PATCH` that return 405.

### D. Test-suite integrity

- No test may pass for the wrong reason. `test_non_deducting_leave_type_returns_zero_restoration`
  was green only because the removed fixture registry happened to agree with the
  intent; it was not testing the configuration it claimed. Assertions should be
  checked for whether they would fail if the behaviour regressed.
- No test may depend on a reused database. `--keepdb` was removed from the
  `README` on 2026-10-02 after it produced 79 phantom failures against a green
  suite.
- Every `docs/*.md` contract referenced from `config/settings/base.py` still
  describes the behaviour it names.

## Out of scope

- **DOCX output.** Deferred with the PDF build; needs `python-docx`.
- **D12 carry-over** — document invalidation on cancellation, and carry-forward
  of an unused annual balance. Both are product decisions, and the first is a
  deliberate one today: the approved document is the historical record of what
  was approved. Changing it needs HR's agreement, not a code change.
- Any new feature.
- Frontend visual or interaction redesign.

## Decisions

- **D1 — The pass may delete code.** A claim with no implementation is removed
  along with the claim, not quietly implemented. The three instances fixed on
  2026-10-02 were all deletions; none of them needed behaviour written.
- **D2 — The pass may not add behaviour.** Where the code is right and the doc is
  wrong, the doc changes. Where the doc states an intended rule that is genuinely
  missing, it is recorded for a decision rather than implemented inside a review.
- **D3 — Findings are recorded whether or not they are fixed.** The tracker gets
  a findings list, so a deferred item is visible rather than lost. This is the
  specific gap that let four red tests ship: the deferred items in D10 of Unit 24
  were named in prose and never revisited.
- **D4 — Verification is per-commit and stated with a command.** Every commit in
  this unit records the exact command and its result. A claim of "verified" with
  no command behind it is itself a finding.

## Verification

The unit is complete when:

1. `uv run manage.py test --noinput` passes on a **fresh** test database, and the
   count is stated.
2. `npm test`, `tsc --noEmit` and `npm run lint` pass, and the count is stated.
3. `manage.py check` and `makemigrations --check` are clean.
4. Every claim named in §A has been traced to code, and the trace is recorded.
5. `context/architecture.md`, `README.md` and `context/progress-tracker.md` agree
   with the code as it now stands.

## Already fixed (2026-10-02, before this spec was written)

- `audit/services.py::_jsonable` could not encode `Decimal`, which psycopg's
  stdlib JSON encoder rejects with `TypeError`. Because an audit entry is written
  inside the owning business transaction, that failure would roll the business
  write back with it. Latent rather than live — the one call site that could carry
  a Decimal already stringified by hand — and now fixed with regression tests.
  Non-finite floats are handled for the same reason from the other direction:
  `json.dumps` *does* emit `NaN`, which PostgreSQL's `jsonb` then rejects.
- `LeaveApplication.row_version` and `leave/services/snapshots.py` removed; see
  §B.
- `architecture.md` §12.3 and §12.11 corrected for one approver per section, and
  the two backend docstrings that stated the superseded rule.