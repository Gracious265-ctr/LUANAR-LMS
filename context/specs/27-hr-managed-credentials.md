# Unit 27 — HR-Managed Credentials

## Goal

Make password accounts the real authentication model and put credential
creation in the right hands:

- a **superuser/admin** creates HR accounts (through the Django admin);
- **HR** creates every other account from the employee directory and sets that
  person's initial password, and can reset it later;
- an ordinary user **cannot change their own password**.

This replaces the Unit 2 assumption that a directory-created employee gets an
**unusable password** and waits for an external identity provider. The product
now issues passwords itself.

## Confirmed decisions

| # | Decision |
|---|----------|
| D1 | **Password accounts are the real model.** `POST /api/v1/auth/login/` authenticates `email` + `password`. `User.username` mirrors `email` so the two can never drift. |
| D2 | **Admin creates HR only.** A superuser creates an `hr` account in the Django admin. HR cannot create, promote to, or edit an `hr` account through the directory API. |
| D3 | **HR sets the initial password.** `POST /api/v1/employees/` requires a `password`; `PATCH` accepts an optional `password` and, when non-blank, resets it. A blank/absent password on update leaves the current one. |
| D4 | **No self-service password change.** There is no endpoint or UI for a logged-in user to change their own password. Only HR (and admin) set passwords. |
| D5 | **Role cannot be changed from the directory.** On create the role is always `employee`; `approver` and `hr` are refused. On update any role change is refused (grant or revoke alike). Approver standing still comes from a team/section appointment, not the account; HR standing comes from the admin. |
| D6 | **Minimum length 8.** A password shorter than 8 characters is refused, whether on create or reset. |

## Design

### Backend (`users`)

`EmployeeSerializer` gains a write-only `password` field.

- **create:** `password` is required and non-blank; `user.set_password(password)`
  (never `set_unusable_password`). The linked `User` is found or created by
  email, with `username = email`.
- **update:** if `password` is present and non-blank, `user.set_password` and
  `save`; otherwise the hash is untouched.
- **role:** create forces `employee` (refuses `approver` / `hr`); update refuses
  any change of role. A no-op value equal to the current role is accepted so an
  existing HR/approver row can still be saved.
- The password is never returned and never enters the audit snapshot.

`users/admin.py` keeps `UserAdmin`, and syncs `username` to `email` on save when
an email is present, so an admin-created HR account can log in through the
email-based login.

### API contract

`POST /api/v1/employees/`

```json
{
  "email": "jane.doe@luanar.ac.mw",
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "initial-password",
  "department": 3,
  "designation": "Lecturer",
  "category": "academic",
  "grade": "E"
}
```

- `password` required, min length 8, write-only.
- `role` optional; only `employee` (or omitted) is accepted.
- 400 with `{"password": ["..."]}` when missing or too short;
  400 with `{"role": ["..."]}` when `approver` or `hr` is requested.

`PATCH /api/v1/employees/{id}/`

- `password` optional; a non-blank value resets it, blank/absent leaves it.
- `role` accepted only when it equals the current role; any change is refused,
  so HR can neither grant nor revoke system access from the directory.

### Frontend

- `lib/employees.ts`: `EmployeeInput.password?: string`.
- `components/hr/employee-form.tsx`:
  - a **Password** field, `required` and `minLength={8}` on create, with the
    helper "Leave blank to keep the current password" on edit;
  - the **Role** control becomes read-only — a fixed "Employee" on create, the
    current role shown on edit — because HR cannot grant `approver` or `hr`.
    `role` is no longer sent in the payload.
- The employee directory and pages are otherwise unchanged.

## Verification

- `uv run manage.py test users` — passwords are usable, login succeeds with an
  HR-set password, missing/short password is refused, HR cannot grant
  `approver`/`hr`, update reset works, blank update keeps the hash.
- `npm test`, `npm run lint`, `npm run typecheck:test`, `npm run build`.

## Out of scope

- Self-service password change and password reset by email.
- Provisioning HR from inside the product UI (admin does it in Django admin).
- Password strength/expiry policy beyond the minimum length.
