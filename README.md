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

```bash
cd backend
uv run manage.py test
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
│   ├── leave/         # Leave domain (stub)
│   ├── workflows/     # Workflows domain (stub)
│   ├── notifications/ # Notifications domain (stub)
│   ├── documents/     # Documents domain (stub)
│   └── audit/         # Audit domain (stub)
├── storage/           # File storage (TBD)
└── context/           # Project documentation
```

## License

[Add license information here]
