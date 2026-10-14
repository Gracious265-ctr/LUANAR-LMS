# LUANAR Leave Management System

Digital leave application and approval system for Lilongwe University of Agriculture and Natural Resources (LUANAR).

## Prerequisites

### Required Software

- **Node.js** 20+ (https://nodejs.org/)
- **Python** 3.12+ (https://www.python.org/)
- **uv** - Python package manager (https://docs.astral.sh/uv/)
- **PostgreSQL** - Database and background task broker (https://www.postgresql.org/)

### Local Installation Notes

#### Windows

1. **PostgreSQL**: Download and install from https://www.postgresql.org/download/windows/. During installation, note the port (default 5432), username (default postgres), and password you set.

2. **Node.js**: Download LTS version from https://nodejs.org/

3. **Python**: Download from https://www.python.org/downloads/

4. **uv**: Install via PowerShell:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

#### macOS (Homebrew)

```bash
brew install postgresql@16 node uv
brew services start postgresql@16
```

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install postgresql python3-dev python3-pip
sudo systemctl start postgresql
```

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd luanar-lms
git checkout development
```

### 2. Database Setup

Create the PostgreSQL database and user:

```sql
CREATE USER luanar WITH PASSWORD 'luanar';
CREATE DATABASE luanar_leave OWNER luanar;
```

### 3. Backend Setup

```bash
cd backend

# Copy environment file
cp .env.example .env

# Edit .env with your database credentials if needed
# Default: postgres://luanar:luanar@localhost:5432/luanar_leave
# Also set the SUPABASE_* file-storage credentials (see "File Storage" below)

# Install dependencies
uv sync

# Run migrations
uv run manage.py migrate

# Start the Django development server
uv run manage.py runserver
```

The backend will be available at http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend

# Copy environment file
cp .env.example .env

# Install dependencies
npm install

# Start the Next.js development server
npm run dev
```

The frontend will be available at http://localhost:3000

### 5. Background Tasks

Django-Q2 uses the PostgreSQL database as the broker — no separate Redis service needed.

In development, tasks run **inline**: `config/settings/development.py` sets
`Q_CLUSTER["sync"] = True`, so `async_task` executes in the approving request
rather than queueing for a worker. Nothing extra to start, and a generated
artifact (such as the approved-leave PDF) is ready by the time the request
returns. Only production needs a supervised worker:

```bash
cd backend

# Production / when you want to exercise the real async path
uv run manage.py qcluster
```

`config.settings.test` pins `sync` back to `False`, because the suite asserts
that a render is *enqueued* and then runs it explicitly.

**Scheduled jobs** (plan housekeeping: lapsing overdue blocks and block
confirmation reminders) are a `django_q.Schedule` row created by
`plans/migrations/0002_schedule_plan_housekeeping.py`, daily at 06:00. A schedule
needs a live worker — `uv run manage.py qcluster` — so run one in any environment
where reminders should actually fire.

### 6. Email Notifications

Every email is one append-only `NotificationOutbox` row: a composer writes the row
and hands it to `notifications/tasks.py`, which is the only module that calls
`send_mail`. Rows start `pending`, move to `sent`/`failed` through the delivery
task, and are inspectable in Django admin (read-only) — so "did the mail go out,
to whom, and if not why?" is answerable without a shell.

Delivery is queued on commit with Django-Q2:

```bash
# in any environment where mail should actually leave the machine
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<gmail address>
EMAIL_HOST_PASSWORD=<app password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=<an address the account may send as>
```

* Without these, `EMAIL_BACKEND` defaults to the console backend and nothing is
  sent — copy `backend/.env.example` for the full list.
* Run `uv run manage.py qcluster` to deliver queued mail, or set
  `NOTIFICATIONS_SYNC_SEND=True` on a single-process dev server to send inline.
* `EMAIL_DEV_RECIPIENT_OVERRIDE` routes every notification to one inbox for
  smoke tests; it is honoured only when `DEBUG=True` and refused otherwise.

### 7. File Storage

Supporting documents and generated approved-leave PDFs are stored in Supabase
Storage. Copy `.env.example` to `.env` and set:

```dotenv
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_BUCKET=leave-documents
```

`SUPABASE_URL` must be the **bare project URL — host only, no path**. The
Supabase dashboard's "Project URL" field ends in `/rest/v1/`, and copying it
verbatim looks correct but breaks storage: `supabase-py` appends its own
`/storage/v1/...` paths, so every request is sent to PostgREST and fails with an
opaque `404` / `PGRST125` that names neither the bucket nor the setting. The
backend rejects a suffixed URL with an actionable message.

The bucket must already exist in the project (Dashboard → Storage).

`SUPABASE_SERVICE_KEY` is the `service_role` key, which **bypasses row-level
security**. Keep it in `.env` only — never in `.env.example` or any committed
file.

Without these the document pipeline cannot store anything: the render task
records the failure on the document row and the UI reports that the document
could not be generated. Everything else in the system works without them.

## First account

There is no seed command and no fixture users. A fresh database has the schema
and **nothing else** — no approver roles, teams, campuses, workflows, leave
types, or accounts. Create the bootstrap administrator to inspect the Django
admin (including the Django-Q2 queue and task results) and to reach
`/dashboard/admin/users`, where HR accounts are created:

```bash
cd backend
uv run manage.py createsuperuser
```

**Use the email address as the `Username`.** The product signs people in by
email and resolves it through the `username` column, so an account whose two
disagree is created and then cannot log in.

`createsuperuser` does not set `User.role`, which defaults to `employee`.
The superuser is the bootstrap administrator outside the product's HR pages:
they create the first HR account through `/dashboard/admin/users` (or
`POST /api/v1/admin-users/`), and HR then creates roles, campuses, teams,
workflows, and leave types through the frontend. If you also want the
superuser to open HR screens directly, set the role once:

```bash
uv run manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='you@luanar.ac.mw')
u.role = 'hr'; u.save()"
```

`/admin/users/user/add/` syncs `username` from `email` on save, so an account
created there is usable without a second step.

### Real users

Real employees need no seed command and no superuser typing a password into
Django admin. HR adds a person on the Employees page and a set-password link is
emailed to them automatically; they follow it, choose their own password, and sign
in. If the mail is lost, the employee's row has a **Send password link** action.

In order: superuser, then employees, then approver roles, then the campus and its
team members, then the financial year.

Once someone is signed in they can change their own password from **My Account**
in the sidebar. It asks for the current password, emails the account a notice,
and signs every session out including the one they changed it from — so they
land back on the sign-in page with a message saying why.

## Running Tests

### Backend

Fast local run (reuses the test DB via `--keepdb`, parallelizes across cores,
MD5 password hasher so user creation is cheap):

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test --keepdb --parallel auto
```

Run one app only (e.g. while working on a single unit):

```bash
DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test workflows --keepdb
```

Parallel sessions (e.g. multiple agents/branches) must use a unique test DB
each or they deadlock on `test_luanar_leave`:

```bash
TEST_DB_NAME=test_luanar_leave_my_branch DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test --keepdb --parallel auto
```

`manage.py test` automatically loads `config.settings.test`, which swaps the
password hasher for a fast one so the suite does not spend most of its time
hashing fixture passwords. Pass `--settings=config.settings.development` to run
against the regular settings instead. Split work across workers when iterating:

```bash
uv run manage.py test --parallel auto
```

Do **not** reuse the test database with `--keepdb`. Rows a previous run left
behind are visible to the next one, and suites that create configuration by id
— approver roles, sections, leave types — then fail on state they did not
create. A reused database reported 79 failures against a green suite. If the
test database already exists from an earlier `--keepdb` run, delete it once:

```bash
uv run manage.py test --noinput
```

If the test runner fails with `permission denied to create database`, the
database role needs the `CREATEDB` privilege (Django creates a temporary test
database):

```sql
ALTER USER luanar CREATEDB;
```

### Frontend

```bash
cd frontend
npm test
```

## API Endpoints

All API endpoints are versioned under `/api/v1/`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login/` | Authenticate user |
| POST | `/api/v1/auth/refresh/` | Refresh access token |
| GET | `/api/v1/auth/me/` | Get current user profile |
| GET | `/api/v1/employees/` | List employee profiles (paginated; `search=`, `ordering=`) |
| POST | `/api/v1/employees/` | Create employee record (and linked user if email is new) |
| GET | `/api/v1/employees/{id}/` | Retrieve one employee profile |
| PATCH | `/api/v1/employees/{id}/` | Update the employee profile (incl. `is_active`) |
| GET | `/api/v1/entitlements/` | List grade/entitlement rules (paginated, newest effective first) |
| POST | `/api/v1/entitlements/` | Create a grade/entitlement rule |
| GET | `/api/v1/entitlements/{id}/` | Retrieve one grade/entitlement rule |
| PATCH | `/api/v1/entitlements/{id}/` | Update a grade/entitlement rule |
| GET | `/api/v1/entitlements/resolve/?grade=B[&as_of=YYYY-MM-DD]` | Resolve a grade to its effective annual entitlement |
| GET | `/api/v1/leave-types/` | List leave types (paginated) |
| POST | `/api/v1/leave-types/` | Create a leave type (code derived from name when blank) |
| GET | `/api/v1/leave-types/{id}/` | Retrieve one leave type |
| PATCH | `/api/v1/leave-types/{id}/` | Update a leave type |
| GET | `/api/v1/leave-rules/` | List leave rules (paginated, newest effective first; `leave_type=`, `effective=current\|upcoming`) |
| POST | `/api/v1/leave-rules/` | Create an effective-dated leave rule |
| GET | `/api/v1/leave-rules/{id}/` | Retrieve one leave rule |
| PATCH | `/api/v1/leave-rules/{id}/` | Update a leave rule |
| GET | `/api/v1/financial-years/` | List financial years (paginated, newest first) |
| POST | `/api/v1/financial-years/` | Create a financial year (must not overlap; activating deactivates the previous active) |
| GET | `/api/v1/financial-years/{id}/` | Retrieve one financial year |
| PATCH | `/api/v1/financial-years/{id}/` | Update a financial year |
| GET | `/api/v1/public-holidays/` | List public holidays (paginated, by date; `year=YYYY` filter) |
| POST | `/api/v1/public-holidays/` | Create a public holiday (date must be unique) |
| GET | `/api/v1/public-holidays/{id}/` | Retrieve one public holiday |
| PATCH | `/api/v1/public-holidays/{id}/` | Update a public holiday |
| GET | `/api/v1/workflows/` | List approval workflows (paginated, by name; each row includes `state`, `effective_from`, `is_active`) |
| POST | `/api/v1/workflows/` | Create a workflow with its ordered approval stages (draft unless `effective_from` is sent; activating/scheduling validates approver availability and scope conflicts) |
| GET | `/api/v1/workflows/{id}/` | Retrieve one workflow with its stages |
| PATCH | `/api/v1/workflows/{id}/` | Update a workflow (replaces its stage list; `effective_from`/`is_active` may be sent with the same activation validation) |
| GET | `/api/v1/delegations/` | List delegation requests (paginated, newest first; `state=` and `approver=` search filters). HR sees every request; an approver sees only the delegations they are a party to |
| POST | `/api/v1/delegations/` | Create a delegation request (approver self-service forces `approver` to the authenticated user; HR can create on behalf) |
| GET | `/api/v1/delegations/{id}/` | Retrieve one delegation (HR sees any; an approver sees only their own, otherwise 404) |
| GET | `/api/v1/delegations/candidates/` | Active approver-role users the caller may nominate as delegate, excluding the caller (approver self-service; avoids opening the HR-only employee list) |
| POST | `/api/v1/delegations/{id}/approve/` | HR approves (mandatory `decision_reason` and `delegate`; rejects period overlap with an approved delegation) |
| POST | `/api/v1/delegations/{id}/reject/` | HR rejects with a mandatory `decision_reason` |
| POST | `/api/v1/delegations/{id}/cancel/` | HR cancels a scheduled/active approved delegation with a mandatory `decision_reason` |
| GET | `/api/v1/reassignments/pending/` | Intervention queue: submitted applications, newest first, with employee, leave type, dates/days, reference, `current_approver`, and the `acting_approver` / `is_delegated` that Unit 21 routing makes authoritative (HR-only) |
| POST | `/api/v1/reassignments/` | Reassign a pending application (`application`, `to_approver`, `reason`); sets `current_approver`, records history, and emails both affected approvers on commit (HR-only) |
| GET | `/api/v1/reassignments/` | Reassignment history, paginated newest first; `application=<uuid>` filter (HR-only) |
| GET | `/api/v1/reassignments/{id}/` | Retrieve one reassignment record (HR-only) |
| GET | `/api/v1/audit-entries/` | Append-only administrative audit log, newest first; filters `action` (dotted code), `target_type` (content-type model), `target_id`, `actor` (HR-only) |
| GET | `/api/v1/audit-entries/{id}/` | Retrieve one audit entry (HR-only) |
| GET | `/api/v1/finalized-leave/` | Organization-wide submitted leave applications, newest `submitted_at` first; `?employee=` search; detail includes documents, reassignment history, and the application audit timeline (HR-only) |
| GET | `/api/v1/finalized-leave/{id}/` | One finalized application with history roll-up; 404 for drafts (HR-only) |
| GET | `/api/v1/leave-document-template/` | Retrieve the single official leave-document template with its read-only field catalog (HR-only; creates the editable default on first access) |
| PATCH | `/api/v1/leave-document-template/` | Update wording, field labels/inclusion/order, and signature areas (HR-only; field keys are validated against the fixed catalog, values are never stored) |
| GET | `/api/v1/audit-entries/` | Administrative audit trail, paginated newest first; immutably records config changes, decisions, and submissions with the acting user. Filters: `action=`, `target_type=`, `target_id=`, `actor=` (HR-only) |
| GET | `/api/v1/audit-entries/{id}/` | Retrieve one audit entry (HR-only) |
| GET | `/api/v1/finalized-leave/` | Finalized (submitted) leave applications, newest submission first, with employee, leave type, dates/days, reference, and current approver; `employee=` name/email search (HR-only) |
| GET | `/api/v1/finalized-leave/{id}/` | One submitted application with its documents, reassignment history, and oldest-first audit trail (HR-only; 404 for draft ids) |
| GET | `/api/v1/leave-applications/{id}/tracking/` | Track an application: full approval workflow, current stage, decisions and activity (owner-only; 404 for others, 409 `application_not_submitted` for drafts) |
| GET | `/api/v1/leave-documents/config/` | Upload-size/type policy (`max_size_bytes`, `allowed_content_types`) for the document UI |
| GET | `/api/v1/leave-applications/{id}/documents/` | List active supporting documents (owner-only; paginated) |
| POST | `/api/v1/leave-applications/{id}/documents/` | Upload a supporting document (draft/rejected/correction_required only; multipart `file`; 409 `document_read_only` otherwise, 400 with `field`/`code`/`message` when rejected) |
| GET | `/api/v1/leave-applications/{id}/documents/{docId}/` | Retrieve one supporting document (owner-only) |
| DELETE | `/api/v1/leave-applications/{id}/documents/{docId}/` | Remove a document: draft hard-deletes the file+row; post-submission retires it and keeps the bytes |
| POST | `/api/v1/leave-applications/{id}/documents/{docId}/replace/` | Replace a document with a new file (draft hard-deletes the old file; post-submission retires `docId` and records `replaced_by`) |
| GET | `/api/v1/leave-applications/{id}/documents/history/` | Document lifecycle snapshot: `active`, `retired` (with `retire_reason`/`replaced_by`), and `document_uploaded`/`document_removed`/`document_replaced` audit events |
| GET | `/api/v1/leave-applications/{id}/documents/{docId}/content/` | Stream a document's bytes (owner or current approver; `?download=1` sets content-disposition; 404 for everyone else) |
| GET | `/api/v1/leave/my/overview/` | Employee dashboard payload: HR profile (grade, designation, department, category, gender, appointment date), annual entitlement/used/available for the current financial year, pending/upcoming leave counts and next leave start (authenticated; balance fields `null` when unset) |
| GET | `/api/v1/leave/my/leave-types/` | Leave types with an effective rule the signed-in user may apply for, with rule hints (max duration, document requirement, min notice, eligibility; authenticated) |

## Git Workflow

- `main` - Production branch
- `development` - Integration branch
- `feature/*` - Feature branches (cut from `development`)

All work happens on `feature/*` branches cut from `development`. Pull requests target `development` and require review before merge.

### Commit Convention

```
<type>(<scope>): <summary>
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

Examples:
- `feat(auth): add JWT login endpoint`
- `fix(balance): correct annual leave calculation`
- `docs(readme): update setup instructions`

## Project Structure

```
luanar-lms/
├── frontend/          # Next.js application
│   ├── app/           # Route handlers and pages
│   ├── components/    # Reusable UI components
│   └── lib/           # Utilities and API client
├── backend/           # Django application
│   ├── config/        # Settings and project config
│   ├── users/         # User model and authentication
│   ├── leave/         # Leave domain (grade entitlements, leave types/rules; applications later)
│   ├── workflows/     # Approval workflow configuration (workflows, stages)
│   ├── notifications/ # Notification outbox + email delivery (django-q2 worker)
│   ├── documents/     # Documents domain (stub)
│   └── audit/         # Audit domain (append-only AuditEvent log + HR finalized-leave/audit views)
├── storage/           # File storage (TBD)
└── context/           # Project documentation
```

## License

[Add license information here]
