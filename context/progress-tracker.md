# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Unit 1 — Project Foundation and Development Contract (COMPLETE)

## Current Goal

- Unit 1 is complete. Ready for review and to begin Unit 2.

## Completed

- Unit 1: Project Foundation and Development Contract
  - Repository structure with development branch
  - Backend: Django 6.1, DRF, JWT auth, custom User model with roles
  - Frontend: Next.js 16, Tailwind CSS v4, design tokens, dashboard shell
  - Auth: Cookie-based JWT proxy via Next.js Route Handlers
  - Django-Q2 background tasks (ORM broker using Postgres, no Redis)
  - PostgreSQL database with migrations
  - Seed command creates 7 test users (one per role)
  - Backend tests (7 tests passing)
  - Frontend tests (4 tests passing)
  - Root README with setup instructions

## In Progress

- None.

## Next Up

- Unit 2 (TBD — will be defined after Unit 1 review)

## Open Questions

- None yet.

## Architecture Decisions

- Python 3.13, Django 6.1, Node 22+, Next.js 16 (App Router, TypeScript)
- `uv` for backend, `npm` for frontend
- Postgres runs natively (no Docker) and also serves as the Django-Q2 broker
- JWT stored as httpOnly cookies via Next.js Route Handlers
- DRF snake_case JSON kept end-to-end
- Light-only theme (no dark mode toggle)
- Inter loaded via next/font/google
- lucide-react as the only icon source
- Tailwind CSS v4 with CSS-based configuration (no tailwind.config.ts)

## Session Notes

- Unit 1 implementation complete
- PostgreSQL 18 installed on Windows, user `luanar` created with `CREATEDB` privilege
- Background tasks use Django-Q2 with Postgres as ORM broker (no Redis)
- Backend: `uv run manage.py test` passes all 7 tests
- Frontend: `npm test` passes all 4 tests
- Development users seeded with password `testpass123`
