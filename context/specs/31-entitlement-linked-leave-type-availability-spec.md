# Unit 31 — Entitlement-Linked Leave Type Availability

## The request

> Annual leave should appear on Leave Type selection in the New Leave Application
> form soon after the HR configures New entitlements/Grades.

## What actually holds today

Verified, not assumed:

| Fact | Holds at |
| --- | --- |
| There is **no** "Annual Leave" row anywhere | `LeaveType` has no seed; `_seed_default_leave_types` was deleted; `seed_dev_users` seeds no business data (`leave/tests/legacy.py:374`) |
| The employee dropdown is every leave type | `EmployeeLeaveTypeViewSet.get_queryset` → `LeaveType.objects.all()` |
| Nothing in the dropdown depends on the employee | the view never reads `request.user`'s profile |
| `GradeEntitlement` cannot name a leave type | `leave/models.py:10-40` — `grade_start`, `grade_end`, `days`, `effective_from`, no FK |
| The entitlement is nonetheless about annual leave | docstring: "Effective-dated **annual leave** entitlement for a grade range" |
| "Annual" elsewhere is real business data, not a name | `LeaveRule.consumes_annual_entitlement` (`leave/providers/database.py:117`) |

So the two halves of the request are each half-built and **disjoint**: `GradeEntitlement`
describes annual leave but cannot say *which* leave type, and the catalog cannot say
*whose*. Configuring a grade band grants days that nothing in the dropdown can spend.
That is the whole defect.

`progress-tracker.md:431-432` and `:437-443` still claim `_seed_default_leave_types`
and `seed_dev_users` seed 4 leave types and 3 entitlement bands. Both claims are
false and are corrected in this unit.

## Decisions

Three questions were put to the user; the answers are binding.

**D1 — `GradeEntitlement` gains a `leave_type` FK, and annual leave is provisioned by
it.** The FK exists so the dropdown offers exactly what HR has granted, but HR does not
*pick* the type for the annual-leave case. Saving an entitlement creates annual leave
and its starting `LeaveRule` on demand (`provision_annual_leave`), which keeps the
standing rule that business data is never seeded (`test_seed_creates_no_business_data`,
and `8d472b3`, which removed a hardcoded annual-leave fallback) — nothing is invented by
a migration, it is created by the HR action that needs it.

This was revised after the first implementation. The original D1 had HR choosing the
leave type in a dropdown, and the "Out of scope" section below said no `LeaveType` row
is ever created. That put the two halves of the request in tension: HR configured a band
and had to go and separately create "Annual Leave" in another form before the dropdown
would show anything. Annual leave is now **owned** by the entitlement form.

The FK is **nullable**. A row with no leave type is the historical meaning — "this
band is the annual leave entitlement" — and migration backfilled existing rows to
`NULL` rather than inventing a `LeaveType`. That fallback still resolves the balance for
rows written before this unit, so it is retained rather than backfilled away.

**D1b — Annual leave is not editable in Leave Types.** Because the entitlement form
creates it, Leave Types would otherwise offer two ways to rename the same thing. The API
refuses to create any type that would claim the annual identity (code `annual` /
`annual-leave`, or name `Annual Leave`) and refuses to edit the canonical type on **any**
field, because a partially-editable type is a trap: `is_active` looks like an ordinary
flag, and retiring annual leave silently empties every employee's leave selection. Other
leave types stay fully editable. Its rule stays editable under Leave Rules, which is
where day caps and balance behaviour are configured.

**D2 — The catalog is filtered by the employee's grade.** A leave type is offered
iff it is active and an effective `GradeEntitlement` names it for a band containing
the employee's grade. The user was told explicitly that this makes the dropdown empty
for an unmapped grade and chose it over the unfiltered option.

**D3 — `LeaveType.is_active`, filtered on.** HR retires a type without deleting it.
Deletion stays impossible: `GradeEntitlement.leave_type` is `PROTECT`, and
`LeaveRule.leave_type` is already `CASCADE`, so deleting a type would silently
destroy its rules.

## What changes

### Overlap becomes per leave type — this is forced, not chosen

`find_overlapping_rule` currently rejects **any** overlapping band. With D1 that is
wrong: HR must be able to say "grade A–C gets 21 days annual *and* 5 compassionate",
which is two rows on the same band. Overlap is therefore checked **within one leave
type**, and `exclude_pk` still skips the row being edited.

Consequence: `resolve_grade_entitlement` becomes ambiguous, because a grade can now
match several effective rows and `max(candidates, key=effective_from)` would pick
whichever happened to be dated last. Resolved rather than left to chance:

- `resolve_grade_entitlement(grade, as_of, leave_type=None)` — narrowed by
  `leave_type` when given. `None` means "any", which is what the `resolve` action
  means when HR does not narrow it.
- `resolve_annual_balance_entitlement(grade, as_of)` — the row that funds the
  balance: one whose leave type's effective `LeaveRule` has
  `consumes_annual_entitlement`, else the untyped row. Latest `effective_from` wins.
- `resolved_annual_entitlement` delegates to it, so the balance path
  (`providers/database.py:146`, `views/me.py:30`) keeps one meaning and one code
  path, and every existing call site and test keeps its signature.

The untyped fallback is what keeps working balances working after the migration. It is
also the documented statement that the balance is one number per employee per year,
not one per leave type — the ledger (`LeaveBalanceTransaction`) is annual-scoped.

If HR marks two leave types as consuming annual entitlement for one grade, the later
`effective_from` funds the balance. That is a configuration ambiguity, and saying so
in the docstring is cheaper than a second ledger.

### The catalog

`leave_types_available_to(grade, as_of)` returns active types with an effective
entitlement covering the grade for that exact type. `EmployeeLeaveTypeViewSet` reads
`request.user`'s profile grade and uses it. `entitlement_days` is added to the
employee serializer so the option reads "Annual Leave — 21 days" rather than making
the employee cross-reference the balance card.

`EmployeeLeaveTypeViewSet` is any-authenticated, not HR-only, so HR is filtered by
**HR's own grade** like everyone else. `test_hr_can_read_the_same_catalog` becomes an
assertion that two users on the same grade see the same list.

### Accepted consequence

Until HR links a leave type to a band, that type is offered to nobody. Maternity,
paternity and compassionate leave are all in this position today, and remain so until
an entitlement names them — annual leave is the only type the entitlement form creates,
because it is the only one an entitlement is about by definition. This is the direct
consequence of D2 and was accepted with it; the empty state says so in words naming
HR, because a bare empty dropdown reads as a broken page.

### Provisioning annual leave

`provision_annual_leave(effective_from, days, actor)` is idempotent and shared by the
API and the Django admin, so annual leave and its first rule exist whichever surface HR
used. It adopts an existing annual type rather than creating a second one, creates the
`LeaveRule` only when the type has none, and records an audit entry for each row it
creates. `GradeEntitlementSerializer.leave_type` is read-only, so a client that posts
one is ignored rather than trusted, and the admin form disables the field.

Canonical annual identity is recognised through `find_annual_leave_type`, which matches
either code `annual` or `annual-leave` or a case-insensitive name `Annual Leave`. Both
codes are honoured because a database written before the canonical code existed holds
annual leave under whichever one it was given.

## Out of scope

- `ANNUAL_CODE = "annual"` in `leave/providers/database.py:32` still decides
  working-day vs calendar-day units. Real per-type units are `20-...` D4's deferred
  assumption and stay deferred.
- The hardcoded fallback bands in `workflows/approval_payloads.py:252` are untouched;
  the grade-dated gap they cover is unchanged by this unit.
- `LeaveApplication.leave_type` stays the soft `PositiveIntegerField` that
  `progress-tracker.md:945-947` already records as a TODO.

## Tests

- Backend: `is_active` defaults true and hides from the employee catalog while
  staying in HR's list; band coverage by grade; unmapped grade; unlinked type offered
  to nobody; `effective_from` in the future does not offer; overlap allowed across
  leave types, refused within one; the balance entitlement prefers the annual type,
  falls back to untyped; `resolve?leave_type=` narrowing; untyped row cannot be
  created once a typed row covers the band.
- Backend, provisioning: creating an entitlement creates the annual type and one
  balance-deducting rule capped at the band's days, and the rule is listed under
  `/api/v1/leave-rules/`; a supplied `leave_type` is ignored because the field is
  read-only; a second band reuses the same type and rule; the generated rows are
  audited; the admin save path provisions identically; the admin leave-type form
  refuses to create or edit annual leave but still allows other types.
- Backend, annual leave ownership: patching the annual type is refused on any field
  including `is_active`, posting the annual name or code is refused, a type sitting on
  code `annual` is guarded too, and patching a non-annual type still succeeds.
- Frontend: the select's loading, error and empty states; the entitlement form has no
  leave-type picker and sends no `leave_type`; the leave-type form refuses to render an
  editable form for annual leave and links to Entitlements; the table shows annual
  leave as "Managed in Entitlements" with an "Edit days" link while other types keep
  their edit action; the table shows the type and marks an unlinked row.