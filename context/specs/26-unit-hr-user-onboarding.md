# Unit — HR-Managed User Onboarding (Set-Password Link)

**Status: implemented, 2026-10-01.** Backend 1198 tests OK, frontend 574 tests OK,
`tsc`/lint clean.

> This document originally specified a *temporary password emailed in plaintext*
> with a `must_change_password` flag. That option was considered and **rejected**;
> what shipped is the single-use set-password link the original draft offered as
> its "Option B". §3 records why, and §12 lists every place the shipped design
> departs from the original draft. Implemented as "Real users, real inboxes" in
> `context/progress-tracker.md`.

## 1. Goal

When HR creates an employee, the account has no password and cannot be signed
into. The system must give that person a way in without a human ever choosing
their password for them, and without any temporary password existing in an
inbox, a mail log, or a database row.

The mechanism is a **single-use link**: HR adds the person, a link is emailed
automatically, they choose their own password with it, and the account is live.
The same link is what `/forgot-password` issues later, so a person who has lost
their password is never a manual task for HR.

Before this unit, `EmployeeSerializer.create` ended in `set_unusable_password()`
and there was no way out: the only options were a superuser typing a password
into Django admin, or the shared `testpass123` from `seed_dev_users`. An
HR-created employee could not authenticate, which meant every notification the
system sends them was undeliverable — the whole point of a queued outbox.

## 2. Scope

In: HR account creation auto-mailing a link; an HR resend action; a
self-service request for a first or forgotten password; the confirm endpoint and
its page; retiring the seeded demo accounts. Change from a live session is a
separate unit, shipped the same day (see §16).

Out: self-service signup, SSO/institutional login (still TBD in
`context/architecture.md`), bulk/CSV import.

Role, grade, department, team and section assignment are unchanged — this unit
only adds the credential flow to the employee-creation form that already exists.

## 3. Why not a temporary password

The original draft proposed generating a 14-character password, emailing it in
plaintext, and forcing a change on first login. It is the conventional approach
and it was rejected, for reasons that are structural rather than stylistic:

* **A plaintext password in an email is a durable credential.** It sits in the
  recipient's mailbox indefinitely, in every backup and forwarding rule of the
  mail server, in the SMTP transaction logs, and in any mail-security gateway
  that archives traffic. It will outlive the change-password prompt that was
  supposed to retire it. The link approach puts an *expiring, single-use,
  hash-stored* artefact in the mail instead — a different class of object.
* **The forced-change gate is a weaker position than having no gate at all.**
  Option A needs `must_change_password`, a `PASSWORD_CHANGE_REQUIRED` permission
  on every endpoint, a JWT that encodes the flag, a frontend interceptor for
  `403`s, and a login-time expiry check — a distributed enforcement mechanism
  that only holds if every one of those pieces is right. Option B needs none of
  it: the account is created with an **unusable password**, so
  `django.contrib.auth.authenticate` cannot succeed and no session ever exists
  to be gated. The link is the only way in, enforced by Django's own auth
  backend rather than by application code.
* **Nothing is lost.** The person still chooses their own password, and the link
  is still time-boxed and single-use.

The cost of Option B is that it needs a new page rather than reusing `/login`,
and that "the account exists but cannot be signed into" is a state that needs
saying out loud in the mail copy. Both were accepted.

## 4. Lifecycle

```
HR adds an employee
        │
        ├─ User(email=…) created with set_unusable_password()   ← cannot sign in
        ├─ EmployeeProfile created
        ├─ audit: CREATED
        ▼
request_password_set(email, actor=HR)
        │
        ├─ outstanding tokens → invalidated_at = now     ← only one link is ever live
        ├─ PasswordSetToken(secret = urlsafe(32 bytes), stored as SHA-256)
        ├─ audit: PASSWORD_SET_REQUESTED (target_type=USER_ACCOUNT)
        └─ NotificationOutbox(user, kind=password_set) → enqueue_delivery on commit
        ▼
Person opens /set-password?token=…
        │
        ├─ validate?token=…  → {"valid": true}       (pre-flight, no password posted)
        ▼
POST confirm { token, password }
        │
        ├─ select_for_update on the token; is_usable() re-checked inside the lock
        ├─ validate_password(password, user)          ← Django's configured validators
        ├─ user.set_password(password)
        ├─ all outstanding tokens → used_at = now
        └─ audit: PASSWORD_SET (self_service=True)
        ▼
Person signs in normally on /login. No session was ever created for them.
```

There is no "flagged account holding a session" state at any point, which is why
there is no permission class to write and nothing to enforce later.

## 5. Data model

`users.PasswordSetToken` (`users/migrations/0007_passwordsettoken.py`):

| Field | Purpose |
|-------|---------|
| `user` | FK to `AUTH_USER_MODEL`, `CASCADE` |
| `token_hash` | SHA-256 hex of the emailed secret, unique. **The secret is never stored.** |
| `expires_at` | Issued at + `PASSWORD_SET_TOKEN_LIFETIME_HOURS` (72) |
| `used_at` | A real consumption |
| `invalidated_at` | Superseded by a newer link, or the account was deactivated |
| `issued_by` | HR who reissued it; `null` when the person asked for it themselves |
| `created_at` | `auto_now_add` |

Indexed on `(user, expires_at)`. `is_usable()` is the **single** definition of
"still good" — unused, uninvalidated, unexpired, and the account still active —
and both the request and confirm paths go through it, so the page's
pre-flight and the commit can never disagree.

`used_at` and `invalidated_at` are deliberately separate. Collapsing them into
one "consumed" timestamp would make "this person set their password" and "HR
reissued their link" indistinguishable in the audit trail months later, which is
exactly the question a password reset invites.

**`User` is unchanged.** No `must_change_password`, no `password_set_at` — the
unusable password *is* the state, and `PasswordSetToken.used_at` is the record.

Audit vocabulary is extended (`audit/migrations/0014`): actions
`PASSWORD_SET_REQUESTED` / `PASSWORD_SET`, and `TargetType.USER_ACCOUNT =
"useraccount"`. This is a deliberate extension of Unit 24's pinned vocabulary
rather than a re-labelling of anything existing.

## 6. Security properties

* **256-bit secret, hash-only.** `secrets.token_urlsafe(32)` from the OS CSPRNG.
  A leaked database row yields nothing usable. Guessing is infeasible; the
  throttles and the expiry are defence in depth, not the thing relied on.
* **One live link per account.** Issuing stamps `invalidated_at` on the
  outstanding tokens, so a link that leaked into an old inbox dies the moment HR
  resends. This also makes resend and reset the same operation.
* **No enumeration.** `request_password_set` returns `None` for an unknown,
  deactivated or address-less account, and the endpoint answers `202` with the
  same fixed body either way. The refusal is logged, never returned.
* **HTTPS or nothing.** `FRONTEND_URL` is deployment configuration that nothing
  validates, so outside `DEBUG` a non-HTTPS base refuses to compose a link at
  all. Failing the HR request is the right outcome; mailing a live secret over
  plain HTTP is not.
* **No auto-login on confirm.** The caller already holds the password, so a
  session there would only add a fixation surface. They sign in themselves.
* **Weak password does not burn the link.** Validators run before the token is
  consumed, so a rejected password can be retried on the same link.
* **Concurrent use is safe.** Confirm takes `select_for_update` on the token and
  re-checks `is_usable()` inside the lock, so two simultaneous submissions
  cannot both set a password.
* **The token leaves the browser URL.** `/set-password` reads it once into a ref
  and scrubs it from the address bar on mount, so it cannot reach browser
  history or a `Referer` header.

## 7. API

| Endpoint | Auth | Throttle | Behaviour |
|----------|------|----------|-----------|
| `POST /api/v1/auth/password-set/request/` | anonymous | `5/hour` | Always `202` + `"If that address has an account, a set-password link is on its way."` |
| `GET /api/v1/auth/password-set/validate/?token=` | anonymous | — | `{"valid": bool}` — pre-flight so nobody types a password into a dead form |
| `POST /api/v1/auth/password-set/confirm/` | anonymous | `20/hour` | `400` + fixed message for any dead token; `400` + validator messages for a weak password |
| `POST /api/v1/employees/{id}/password-set-link/` | HR only | viewset | `202`; `400` if no address or deactivated |

All token rejections share one exception and one message — unknown, expired,
used, superseded and deactivated are indistinguishable, because the legitimate
holder cannot fix any of them except by asking for a fresh link.

The request throttle exists because each accepted request sends a real email: it
is what stops a shared or spoofed origin turning the endpoint into a mail cannon.
The confirm throttle bounds attempts against a leaked token value.

Frontend calls go through three same-origin Next.js proxies, so the Django URL
never reaches the browser:

* `app/api/auth/password-set/request/route.ts`
* `app/api/auth/password-set/validate/route.ts`
* `app/api/auth/password-set/confirm/route.ts`

## 8. Email

The outbox gained a `user` subject family (`notifications/migrations/0007`),
composed by `notifications/accounts.py` and dispatched through the same single
send site as every other notification, so it retries, records `sent`/`failed`
and honours `EMAIL_DEV_RECIPIENT_OVERRIDE`.

* **Subject:** `Set your LUANAR Leave password` — no "password" in the subject
  line, which is a spam/phishing trigger.
* **Body:** plain text, low alarm. States that no one set their password and no
  one will, gives the link and the expiry, names both routes to a replacement
  (ask HR, or the sign-in page), and closes with "If you were not expecting this
  message, ignore it and tell HR."
* **No unique constraint on this family, deliberately.** Every other subject
  family is idempotent by a partial unique constraint, because a re-emitted
  business event must not send twice. A *resent* link must send again, so
  `queue_password_set_email` is a plain `create`, one row per issuance. Single
  use is guaranteed by the token, not by a constraint — which is the right layer
  for it, since the token is what a leaked row would not contain anyway.
* An account with no address is logged and skipped rather than producing an
  undeliverable row.

## 9. HR's side

* **First link:** automatic on employee creation, gated on
  `not user.has_usable_password()`. Attaching an employee record to somebody who
  already has a password must never mail them a reset link.
* **Resend:** the employee row's **Send password link** action. Issuing
  invalidates the previous link, so it doubles as "reset their link".
* **Never show a secret.** There is no password to show HR, which removes the
  original draft's `__3.9` requirement about the temp password never appearing in
  the UI entirely.
* **In order:** superuser → employees → approver roles → team and members →
  financial year. `seed_dev_users` remains the fast way to get leave types,
  entitlements, rules and the financial year in place.

## 10. Frontend

* `lib/password-set.ts` — `requestPasswordSetLink`, `validatePasswordSetToken`,
  `confirmPasswordSet`.
* `app/(auth)/set-password/page.tsx` — pre-flight, URL scrubbing, password +
  strength hint, then a redirect to `/login` on success.
* `app/(auth)/forgot-password/page.tsx` — the self-service request.
* `app/(auth)/login/page.tsx` — a "Forgot your password?" link.

No global `403` interceptor exists, and none is needed: there is no
partially-authenticated state for it to catch.

## 11. Retiring the demo accounts

`uv run manage.py retire_demo_users` deactivates the seven `@test.luanar`
accounts and strips their passwords, one `DEACTIVATED` audit entry each
(actor-less — a maintenance command, not a person). Idempotent; `--undo`
restores the demo state.

Deletion was the obvious answer and is not available: roughly two dozen foreign
keys point at `users.User` with `PROTECT` (audit entries, approval decisions,
delegations, reassignments, `RoleAssignment`, `SectionMember`, balance
transactions), so a demo account with any history refuses to be deleted at all —
pinned by `test_deleting_the_account_instead_is_refused`. Deactivation achieves
what is actually wanted: no authentication, and no approver routing
(`workflows/services.py:344` gates on `is_active`), with every row left in
place. Re-running `seed_dev_users` cannot revive them, because its
`update_or_create` never touches `is_active`.

## 12. Defect found and fixed: form-encoded `is_active`

**Creating an employee over form-encoded multipart produced a *deactivated*
account.** DRF's `BooleanField` sets `default_empty_html = False`, which is
correct for an HTML form (an unchecked checkbox is absent and means False) and
wrong for an optional API field: any client posting multipart or form-encoded —
`curl -F`, a plain HTML form, DRF's own test client by default — omits
`is_active` entirely, and DRF supplied `False`. `EmployeeSerializer.create` then
built the user with `is_active=False`, so the new employee had no way in and no
way to be noticed.

Worse, `test_a_hr_created_employee_is_inactive_so_holds_no_approver_roles` had
come to *assert* the accident, encoding the bug as intended behaviour.

Fixed with `OptionalBooleanField` (absent means "leave it alone") and an
`initial_data` check in `update()` so a PATCH that never mentioned activation
cannot flip an account back off or on. The old test was rewritten: a new account
holds no approver roles because it has no role assignment, not because it was
switched off.

## 13. Deviations from the original draft

| Original draft | Shipped | Why |
|----------------|---------|-----|
| 14-char temp password emailed in plaintext (§2.4, §2.7) | No password is ever generated or mailed | §3 — a plaintext credential outlives the prompt meant to retire it |
| `must_change_password` + `password_set_at` columns (§3.1) | Neither; the unusable password is the state | §3 — one fewer thing to keep consistent |
| Global `PasswordChangeRequired` permission (§3.7) | Not needed — `authenticate()` cannot succeed without a usable password | §3 — enforced by Django, not by a gate someone must remember to apply |
| `TEMP_PASSWORD_EXPIRED` at login, 48h (§2.5, §3.6) | 72h token expiry, checked on the token | No login step exists to intercept; the artefact that expires is the link |
| `TEMP_PASSWORD_EXPIRY_HOURS = 48` (§3.10) | `PASSWORD_SET_TOKEN_LIFETIME_HOURS = 72` | 72h reads at a human pace, and a link is a narrower secret than a password |
| Resend rotates a temp password, overwriting the hash (§3.4) | Resend issues a new link, invalidating the old token | Same guarantee; the old link dies even if it was read |
| `/change-password` endpoint (§3.8) | Two endpoints with different contracts: `/password-set/confirm/` (token-based, for the first or a forgotten password) and `/password-change/` (session-based, for a signed-in user, shipped later) | §3.8's version existed only to serve the forced-change prompt, and there is no such prompt. The second was added on its own terms — re-authentication instead of a token, and session eviction, which §3.8 never had to think about |
| Global `403 PASSWORD_CHANGE_REQUIRED` interceptor (§3.9) | None | There is no session to intercept |
| Audit `user.created_by_hr` / `user.welcome_email_resent` / `user.password_changed_first_login` (§3.11) | `PASSWORD_SET_REQUESTED` / `PASSWORD_SET` on `USER_ACCOUNT` | Added to Unit 24's vocabulary rather than replacing it |
| Password reset for existing users out of scope (§6) | In scope — `/forgot-password` | Same mechanism, and a new employee who cannot sign in is the same failure either way |

## 14. Tests

`users/tests_password_set.py` — 46 tests:

* `TokenIssuanceTests` — hash-only storage, secret never persisted, 72h expiry,
  one live link, superseding, self-service vs HR `issued_by`, no address, no
  enumeration, outbox row + queueing, HTTP/HTTPS refusal, unconfigured
  `FRONTEND_URL`, inactive accounts, retry independence.
* `ConfirmPasswordTests` — sets the password, consumes every outstanding token,
  expired/used/invalidated/unknown/deactivated rejection, weak password rejected
  **without** consuming, validators, re-confirm fails, no auto-login.
* `PasswordSetEndpointTests` — identical `202` for known and unknown addresses,
  validate endpoint, confirm endpoint error shapes, throttles, method/permission
  behaviour.
* `EmployeePasswordLinkTests` — auto-send on create, no mail when a password
  already exists, resend action, HR-only, no-address and deactivated refusals.
* `RetireDemoUsersCommandTests` — idempotent, `--undo`, no deletion, history
  preserved, audit written, non-demo accounts untouched.
* `NoDemoAccountsTests` — `test_it_reports_nothing_to_do`: on a database
  that never had the seed run, a real account is left alone and the command says so.

Plus the `is_active` regression pair in `users/tests.py`.

Frontend: `tests/password-set-pages.test.tsx` (9) and
`tests/password-set-proxy.test.ts` (5) — the proxy tests read the same
`process.env.DJANGO_API_URL` default the routes do and spy on `globalThis.fetch`
rather than replacing a module-scope binding.

## 15. Verification

```
backend:  manage.py check                     no issues
          makemigrations --check --dry-run     No changes detected
          migrate                             users/0007, notifications/0007, audit/0014
          manage.py test                      1198 tests OK  (was 1151)
frontend: npx tsc --noEmit                    clean
          npm run lint                        clean
          npm test                            75 files, 574 tests OK  (was 560)
```

## 16. Operational requirements

* `FRONTEND_URL` in `backend/.env`, HTTPS in any non-`DEBUG` deployment.
* `EMAIL_BACKEND` / host / port / `EMAIL_HOST_USER` / App Password /
  `EMAIL_USE_TLS` / `DEFAULT_FROM_EMAIL` (an address the SMTP account is
  authorised to send as).
* A worker for queued mail: `uv run manage.py qcluster`, or
  `NOTIFICATIONS_SYNC_SEND=True` for a single-process dev server.

**Resolved — self-service password change shipped 2026-10-01.** An already
signed-in user can now change their own password from **My Account**
(`/dashboard/account`), via `POST /api/v1/auth/password-change/`. It re-checks
the current password, emails the account a notice, and signs every session out
including the one that made the change. Session eviction depends on
`CHECK_REVOKE_TOKEN` plus a refresh-path check in `users/authentication.py`, and
is documented under "Completed — Change password for a signed-in user" in
`context/progress-tracker.md`.

**Still open.** Live SMTP has not been verified. Two checks, and they are not
interchangeable:

1. **Transport** — `manage.py sendtestemail <recipient>` (Django's built-in
   command) proves the credentials, the TLS negotiation and the `From:` address
   are accepted. It sends directly and **bypasses the outbox entirely**, so a
   green result says nothing about the queued pipeline.
2. **The pipeline** — create an employee and watch one outbox row go
   `pending → sent`, which proves `enqueue_delivery`, the worker, the composer
   and the transport together. With the seeded `@test.luanar` addresses this
   always fails on a real relay, so it needs `EMAIL_DEV_RECIPIENT_OVERRIDE` set
   to a real inbox, or a real employee record.

Real notification routing also needs actual employees, approver roles, teams,
members and a financial year configured; none exist yet.
