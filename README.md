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

# Install dependencies
uv sync

# Run migrations
uv run manage.py migrate

# Seed development users
uv run manage.py seed_dev_users

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

### 5. Background Tasks (Optional for Development)

Django-Q2 uses the PostgreSQL database as the broker — no separate Redis service needed.

```bash
cd backend

# Start the Django-Q2 cluster worker
uv run manage.py qcluster
```

## Development Users

The seed command creates one user per role with password `testpass123`:

| Role | Email |
|------|-------|
| Employee | employee@test.luanar |
| Supervisor | supervisor@test.luanar |
| Head of Department | hod@test.luanar |
| Dean | dean@test.luanar |
| Registrar | registrar@test.luanar |
| Deputy Vice-Chancellor | dvc@test.luanar |
| Human Resources | hr@test.luanar |

### Admin / Django-Q2 task inspection

The seed command does not create a superuser. Create one to inspect the Django
admin (including the Django-Q2 queue and task results):

```bash
cd backend
uv run manage.py createsuperuser
```

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
| GET | `/api/v1/delegations/` | List delegation requests (HR-only, paginated, newest first; `state=` and `approver=` search filters) |
| POST | `/api/v1/delegations/` | Create a delegation request (approver self-service forces `approver` to the authenticated user; HR can create on behalf) |
| GET | `/api/v1/delegations/{id}/` | Retrieve one delegation (HR-only) |
| POST | `/api/v1/delegations/{id}/approve/` | HR approves (mandatory `decision_reason` and `delegate`; rejects period overlap with an approved delegation) |
| POST | `/api/v1/delegations/{id}/reject/` | HR rejects with a mandatory `decision_reason` |
| POST | `/api/v1/delegations/{id}/cancel/` | HR cancels a scheduled/active approved delegation with a mandatory `decision_reason` |
| GET | `/api/v1/reassignments/pending/` | Intervention queue: submitted applications, newest first, with employee, leave type, dates/days, reference, and `current_approver` (HR-only) |
| POST | `/api/v1/reassignments/` | Reassign a pending application (`application`, `to_approver`, `reason`); sets `current_approver` and records history (HR-only) |
| GET | `/api/v1/reassignments/` | Reassignment history, paginated newest first; `application=<uuid>` filter (HR-only) |
| GET | `/api/v1/reassignments/{id}/` | Retrieve one reassignment record (HR-only) |
| GET | `/api/v1/leave-document-template/` | Retrieve the single official leave-document template with its read-only field catalog (HR-only; creates the editable default on first access) |
| PATCH | `/api/v1/leave-document-template/` | Update wording, field labels/inclusion/order, and signature areas (HR-only; field keys are validated against the fixed catalog, values are never stored) |
| GET | `/api/v1/leave-applications/{id}/tracking/` | Track an application: full approval workflow, current stage, decisions and activity (owner-only; 404 for others, 409 `application_not_submitted` for drafts) |

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
│   ├── notifications/ # Notifications domain (stub)
│   ├── documents/     # Documents domain (stub)
│   └── audit/         # Audit domain (stub)
├── storage/           # File storage (TBD)
└── context/           # Project documentation
```

## License

[Add license information here]
