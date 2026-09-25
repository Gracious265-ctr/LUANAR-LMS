# Unit 22 — Email Notifications (Detailed Design)

**Scope:** employee + approver email notifications for the leave approval loop.
**Status:** Phase 1 — spec drafted; **do not begin Phase 2 (implementation) until
the developer approves.** Replaces the deferred tracker entry (the Section-3.6
thread in Unit 23's spec flagged this unit as "not to be begun" — the developer
has now explicitly overruled that and selected Unit 22 as next).

---

## 1. Context recap

The leave approval loop has three hard seams that Unit 22 must keep honest:

* **`workflows/events.py`** is a **no-op approval-event bus**: `emit_approval_event`
  returns `None` (Unit 16 no-op sink). The dataclass `ApprovalEvent` and constants
  `DECISION_RECORDED` / `APPLICATION_FINALISED` already exist, but nothing is
  ever emitted for real. Unit 22 **wires the real bus** — this is the place
  where "later units connect real consumers" (per its docstring) finally happens.
* **`backend/notifications/`** exists as an app shell: `AppConfig` only — no
  model, no migration, no views. Unit 22 adds the notification seams here.
* **`EMAIL_BACKEND`** is `django.core.mail.backends.console.EmailBackend` in
  base settings. Unit 22 keeps that default for tests (no real SMTP), and the
  test suite asserts on the **captured outbox** (`django.core.mail.outbox`)
  rather than real delivery.

Reference vocabulary already in the codebase (reuse, do not invent):

* `CancellationRequest.NotificationState` — `pending` / `sent` / `failed`
  (leave/cancellations/models.py:33). The same _delivery-state_ vocabulary is
  the natural fit for each email attempt.

## 2. Decisions (D1–D8)

* **D1 — No new tracking event type.** The payload vocabulary is pinned in
  Unit 21 (D11): don't add `notification_sent` etc. to the workflow event bus.
  Email delivery state is recorded on the notification record, **not** as a new
  event.
* **D2 — Bus becomes real — once.** `events.py` gains a private `_consumers`
  registry + `_emit_real` seam (the exact pattern Unit 23's finalise consumer
  already anticipated). `emit_approval_event` becomes: run consumers on
  `transaction.on_commit`. Unit 22 registers its email consumer; later units
  register theirs on the same registry. No event ever fires twice for the same
  (kind, application_id, stage_order) — idempotency by outbox row
  (see D6).
* **D3 — When to send.** On `DECISION_RECORDED` (rejection, correction request)
  and on `APPLICATION_FINALISED` (final approval). The submitted payload drives
  composer; no bespoke templating engine — use the persisted `ApprovalEvent`
  atoms (role_label, approver_name, comment, stage_order, reference_number,
  submission_cycle) directly.
* **D4 — Recipient list.** Authoritative `get_view_access`-style seam from
  Unit 16: employee (owner) + `current_approver` / HR. For `DECISION_RECORDED`
  → the employee; for `APPLICATION_FINALISED` → employee + HR approvers who
  decided. No role-scrape, no fixture guesswork — reuse the chain of
  `ApplicationStage` rows already persisted.
* **D5 — Append-only outbox.** New `notifications/` app gains one append-only
  model (`NotificationOutbox`), locked against update/delete (mirrors the
  balance-ledger discipline). Idempotent per (kind, application, cycle, role) so
  re-emits after reconnect never duplicate.
* **D6 — Delivery + state.** `send_mail` with `EMAIL_BACKEND=console` in dev;
  the service returns/sets `pending → sent | failed` on the outbox row from the
  real exception outcome intrusion seam. Console backend prints but Django's
  `mail.outbox` captures it for tests; failure path raises a typed error that is
  recorded as `failed` (not swallowed silently).
* **D7 — No new audit vocabulary.** Audit `Action` stays as pinned in
  Unit 19/23; email outcomes are outbox state, not audit events (auditing the
  *decision* is already done in Unit 23).
* **D8 — Out of scope.** Attachments (document goes out via the Unit 23 signed
  URL instead), HTML templates with themes, batching/digests, unsubscribe.

## 3. Reconciliation with real vs drafted seams

Phase-1 verification found the **draft seam expectations were wrong**, matching
the Unit-23 review finding:

* The draft assumed `workflows/events.py` already had `_consumers`/`_emit_real` —
  **it does not** (36 lines, no-op sink). D2 now makes Unit 22 the unit that
  adds the real bus, as its docstring always promised.
* The draft assumed a `notifications` app with a model + migration — it is an
  empty AppConfig shell. D5 now owns creating the outbox model + migration.
* `FIELD_CATALOG`/document rendering is **not** touched (that's Unit 23's
  domain, already done); email reuses snapshot atoms instead.
* The code-anchored vocabulary (`NotificationState`, `EMAIL_BACKEND`, `outbox`)
  is real and unchanged.

## 4. Deliverables (when approved — Phase 2)

* `notifications/` app: append-only `NotificationOutbox` model + migration +
  append-only manager (update/delete locked).
* `notifications/services.py`: `compose_and_dispatch(kind, application, cycle)`
  → renders subject/body from `ApprovalEvent` atoms, writes the outbox row
  (get_or_create), calls `send_mail` (console backend), sets state= sent/failed.
* `workflows/events.py`: real `_consumers` registry + `_emit_real` + call on
  `transaction.on_commit`; `emit_approval_event` now dispatches. Register the
  Unit-22 email consumer (self, on DECISION_RECORDED + APPLICATION_FINALISED).
* `notifications/tests.py`: bus idempotency, recipient matrix (employee vs HR),
  state transitions, failure path (failed state), no duplicate rows on re-emit.
* Tracker: mark Unit 22 complete; Next Up = Unit 24 (delegation routing).

**Awaiting developer approval before Phase 2 begins (per §20 discipline).**
