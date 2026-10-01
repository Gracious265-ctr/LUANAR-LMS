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

---

## 5. Phase 3 — as built (delivery made real)

Unit 22 shipped the outbox and the bus as specified above, but the **transport was
never finished**: `EMAIL_BACKEND` stayed hard-coded to the console backend, the
composers called `send_mail` inline from whatever request happened to emit the
event, and `employee_notification_state` on a cancellation request could never move
because `leave/cancellations/events.py` was still the Unit-18 no-op sink. Mail that
"was established" therefore never reached anybody. This section records the delta.

### 5.1 Deltas to D6

D6 ("`send_mail` with `EMAIL_BACKEND=console` in dev, set state from the real
exception outcome") assumed the send happens inside the service. That was the
reason notifications failed quietly: a synchronous send ties mail delivery to a web
request and to whatever relay happens to answer it.

As built:

* **Transport is env-configured.** `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`,
  `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`,
  `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL` are read in `config/settings/base.py`. With
  none set the console backend remains the default, so no credential is required to
  develop and nothing silently ships a hard-coded relay.
* **`tasks.py` is the single send site.** No composer imports `send_mail`. Each
  composer writes an append-only row and calls `enqueue_delivery()`.
* **Delivery is queued on commit** with Django-Q2 (the ORM broker already required by
  §8 of the architecture doc): `async_task("notifications.tasks.deliver_notification",
  row_id, recipients)`. A row is `pending` until a worker runs it; `NOTIFICATIONS_SYNC_SEND=True`
  runs it inline for a single-process dev server.
* **Failure isolation is the same discipline, moved.** The task re-reads the row,
  records `failed` + the error, logs, and never raises — so a broker outage or a
  dead relay cannot undo a decision that already committed.
* **`DEFAULT_FROM_EMAIL` is validated against the transport.** Gmail rejects a
  `From:` the account is not authorised to send as, which would otherwise fill the
  outbox with unexplained 550s; with SMTP and no `DEFAULT_FROM_EMAIL` the row records
  `failed` with that explanation.

### 5.2 New subject family: cancellations

The cancellation bus is now a real registry (`register_consumer` /
`emit_cancellation_event`, mirroring `workflows/events.py`), and
`notifications/cancellations.py` composes one email per event for the employee.
`NotificationOutbox` gains a `cancellation` FK plus the
`one_outbox_row_per_cancellation_kind_role` constraint, so idempotency follows the
same rule as every other family.

This family uniquely keeps a second, user-facing state column:
`CancellationRequest.employee_notification_state`. The composer marks it `pending`
when it queues, and `deliver_notification` reconciles it to `sent`/`failed` after
the attempt, so the request and the outbox can never disagree.

### 5.3 Scheduled reminders

Plan housekeeping (`plans.tasks.run_plan_housekeeping` — lapsing overdue blocks and
block-confirmation reminders) is a `django_q.Schedule` row created by
`plans/migrations/0002_schedule_plan_housekeeping.py` (daily 06:00). Reminder emails
were never sent because nothing scheduled the job. A schedule needs a live
`qcluster`; `Q_CLUSTER["sync"]` does not affect cron rows.

### 5.4 Operations

* **Read-only admin** (`notifications/admin.py`): the outbox is inspectable by
  HR/support (state, recipient, error) and cannot be edited by hand, matching its
  append-only rule.
* **`EMAIL_DEV_RECIPIENT_OVERRIDE`** routes every notification to one real inbox so
  SMTP can be smoke-tested against seeded `@test.luanar` addresses. Honoured only
  when `DEBUG=True`; with `DEBUG=False` it is refused and logged as an error.
* **Tests** pin the two halves apart: a queue call leaves the row `pending`, and
  `deliver_notification(row.pk, recipients=[...])` is what sends. `notifications/`
  covers all five families, plus transport-level cases (override gate, `From:`
  validation, broker outage, idempotent re-delivery).

## 6. As-built addition: the account family (2026-10-01)

The families above all describe something that happened to a person. The outbox
also carries one email about a login itself: the **set-password link** a new
employee needs, because HR creates accounts without a password and cannot know
one.

* **Subject** — `user` (`NotificationOutbox.user`, `notifications/migrations/
  0007`), the only row about a login rather than a business event. The check
  constraint gained a seventh arm so a row still has exactly one subject.
* **No unique constraint, deliberately.** Every other family is idempotent by a
  partial unique constraint, because a re-emitted event must not send twice. A
  *resent* link must send again, so the account family has no such constraint and
  keeps one row per issuance. Single use is guaranteed by the token instead
  (`users.PasswordSetToken`: 72h, only its SHA-256 stored, invalidated when
  superseded and consumed on use).
* **Composer** — `notifications/accounts.py`, queued through the same single send
  site, so it retries, records `sent`/`failed`, and honours the development
  recipient override like everything else.
* **Security posture** — the request endpoint answers identically for every
  address (no enumeration), is throttled at 5/hour because each accepted request
  mails a real person, and refuses to build a link over plain HTTP outside
  `DEBUG`. The token is scrubbed from the URL in the browser on arrival.
* **Audit** — `PASSWORD_SET_REQUESTED` / `PASSWORD_SET` on a `USER_ACCOUNT`
  target, extending the Unit 24 vocabulary deliberately: "who asked for this and
  when" is the question a password reset always invites later.
