# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Unit 13 — Leave Application and Drafts (COMPLETE)

## Current Goal

- Unit 13 is complete. Ready for review and to begin next unit.

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

- Unit 13: Leave Application and Drafts
  - Backend: LeaveApplication + SupportingDocument + ReferenceSequence models
  - Backend: Working-days stub (weekend exclusion only, holiday stub deferred to Unit 5)
  - Backend: Supabase storage service (upload/delete)
  - Backend: Serializers, IsOwner permission, DRF ModelViewSet
  - Backend: Leave app URL routing via DRF DefaultRouter
  - Backend: preview-days endpoint for live working-day calculation
  - Backend: submit endpoint with LUANAR-{YYYY}-{5-digit} reference numbers
  - Backend: Submit validation (leave_type, dates, reason required)
  - Backend: Immutability enforcement (submitted apps cannot be edited/deleted)
  - Backend: Supabase settings in settings.py (SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET)
  - Backend: 28 leave tests passing (working days, models, API, permissions, documents)
  - Frontend: Service layer (leaveTypes mock, calendarRules API proxy)
  - Frontend: API route handlers proxying to Django for all leave endpoints
  - Frontend: useLeaveApplications, useLeaveApplication, useAutosaveDraft hooks
  - Frontend: LeaveTypeSelect, DateRangeFields, WorkingDaysPreview components
  - Frontend: SupportingDocumentsUploader with react-dropzone
  - Frontend: LeaveApplicationForm with autosave on first interaction
  - Frontend: DraftsList, DraftCard with edit/delete/review actions
  - Frontend: ReviewSummary with submit button and reference number display
  - Frontend: Leave pages (new, edit, review, drafts) under /dashboard/leave/
  - Frontend: Updated dashboard shell sidebar links
  - Frontend: 4 existing tests pass, TypeScript clean, build succeeds

## Next Up

- Unit 4 (Leave Types API) and Unit 5 (Calendar/Rules API) — deferred per Unit 13 spec

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

- Unit 13 implementation complete
- Backend: 28 leave tests pass (working days, models, API, permissions, documents)
- Backend: 7 existing user tests still pass
- Backend: Migration `leave/0001_initial.py` created
- Frontend: 4 existing tests still pass, TypeScript clean, build succeeds
- Frontend dependencies added: date-fns, react-dropzone
- Backend dependencies added: supabase
- LeaveType FK is soft reference (PositiveIntegerField) — documented TODO(unit-4)
- Working-days stub excludes weekends only — documented TODO(unit-5)
- Reference number format: LUANAR-{YYYY}-{5-digit sequence}
- Document storage uses Supabase — requires env vars SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET

- Code review completed (Standards + Spec axes)
  - Fixed bare except:pass in views.py (now logs with logger.exception)
  - Removed dead perform_update code
  - Fixed useState side-effect in ReviewSummary.tsx → useEffect
  - Removed scope-creep head-level Edit link in ReviewSummary
  - Switched storage.py from get_public_url to signed URLs (configurable expiry)
  - Fixed DraftCard showing raw leave type ID → resolved name via useEffect
- Fixed upload button not visible on /new page
  - SupportingDocumentsUploader: dropzone renders unconditionally
  - Added onEnsureDraft prop for lazy draft creation
  - Removed router.replace from ensureDraftCreated (was unmounting component mid-upload)
- Supabase credentials configured in .env, bucket leave-documents created
- Fixed sidebar active state — derived from usePathname() instead of click-only state
- Git guardrails skill installed (mattpocock/skills@git-guardrails-claude-code)
