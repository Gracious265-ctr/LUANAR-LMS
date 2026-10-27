

# Code Standards

These standards are mandatory for everyone working on the LUANAR Leave Management System, including all human developers, AI coding agents, and any other automated development tools.

These rules apply across all branches and environments. Code that violates these standards must be corrected before it is considered complete.

## General

- Follow the system boundaries defined in `architecture.md`.
- Keep modules small and single-purpose.
- Give every module, function, class, and component one clear responsibility.
- Fix root causes instead of layering workarounds over existing problems.
- Do not introduce duplicate implementations of the same business rule.
- Do not mix unrelated concerns in the same module, component, service, or API endpoint.
- Keep business rules in the backend; never rely on frontend logic for authoritative decisions.
- Do not bypass existing application services, validation, authorization, or workflow logic to make a feature work.
- Do not introduce a new dependency when an existing project dependency already provides the required functionality.
- Do not add speculative abstractions for functionality that does not yet exist.
- Do not leave dead code, unused imports, temporary debugging code, or commented-out implementations.
- Do not silently change existing behavior while implementing an unrelated feature.
- Preserve existing functionality unless the change explicitly requires modifying it.
- Do not duplicate constants, configuration values, or business rules across multiple files.
- Use descriptive names that communicate purpose.
- Avoid abbreviations unless they are established project or domain terminology.
- Functions must be short enough that their primary responsibility is immediately understandable.
- Complex logic must be extracted into appropriately named functions, services, or modules.
- Do not hide business logic inside UI components.
- Do not hide database operations inside frontend code.
- Do not commit secrets, passwords, API keys, tokens, or credentials.
- Environment-specific values must be supplied through environment configuration.
- Never use production credentials in development or testing code.
- Do not modify architecture, database structure, workflow rules, or other permanent project decisions without updating the relevant documentation.
- Every completed implementation must leave the codebase in a buildable and testable state.
- Do not mark work as complete when required verification has not been performed.

## TypeScript

- TypeScript must use strict type checking.
- `any` is prohibited unless there is a documented and unavoidable external-library limitation.
- Prefer explicit types over inferred types when the type communicates an important business contract.
- Use `interface` for object contracts.
- Use `type` for unions, intersections, mapped types, and other type compositions.
- Do not use type assertions to suppress legitimate type errors.
- `as any` is prohibited.
- Validate `unknown` external data before using it.
- API responses must have explicit types.
- Form data must have explicit types.
- Component props must have explicit types.
- Do not duplicate the same interface in multiple files.
- Shared domain types must have one authoritative definition.
- Use discriminated unions for state machines and mutually exclusive states where appropriate.
- Use `null` and `undefined` consistently according to the project's established API contract; do not mix representations arbitrarily.
- Do not use non-null assertions (`!`) unless the invariant guaranteeing the value is non-null is explicit and unavoidable.
- Avoid deeply nested conditional expressions.
- Use descriptive enum values or string unions for domain states.
- Do not represent important domain states using arbitrary strings scattered throughout the codebase.

## Next.js

- Next.js is responsible for the web application and presentation layer.
- Follow the App Router architecture.
- Default to React Server Components.
- Add `"use client"` only when browser interactivity, hooks, browser APIs, or client-side state requires it.
- Do not add `"use client"` to parent components when only a child requires client-side behavior.
- Keep Server Components focused on rendering and server-side data composition.
- Client Components must not contain authoritative business rules.
- Do not access the database directly from frontend components.
- Do not access Django internals from frontend components.
- Frontend communication with the backend must use the defined API boundary.
- Keep page components focused on page composition.
- Reusable UI belongs in `components/`.
- Shared frontend utilities belong in appropriate utility modules.
- Do not place large business workflows inside page components.
- Do not use frontend routing as a substitute for backend authorization.
- Loading, error, empty, and success states must be explicitly handled for asynchronous operations.
- Do not expose sensitive backend data to the browser unless the user is authorized to receive it.
- Browser-only APIs must only be accessed from client components.
- Do not perform long-running processing inside browser requests.
- Long-running processing must be handled by backend/background processing.

## React

- Components must have one clear responsibility.
- Prefer composition over large conditional components.
- Keep components small and readable.
- Props must be explicitly typed.
- Do not duplicate UI logic across components.
- Reusable behavior must be extracted when duplication becomes meaningful.
- Do not place API calls, database logic, or business-rule calculations directly inside presentational components.
- Do not mutate props.
- Do not mutate React state directly.
- Use stable keys when rendering lists.
- Do not use array indexes as React keys when a stable domain identifier exists.
- Hooks must follow the Rules of Hooks.
- Do not create custom hooks merely to wrap a single trivial operation.
- Client state must only contain information that actually requires client-side state.
- Server state must use the project's established server-state/data-fetching approach rather than being duplicated across local component state.

## shadcn/ui

- Use shadcn/ui components as the primary reusable UI component foundation.
- Reuse existing shadcn/ui components before creating new primitive components.
- Do not install or create duplicate components when an existing component satisfies the requirement.
- Custom components must compose existing primitives where appropriate.
- Preserve consistent component behavior across the application.
- Do not place business logic inside reusable UI primitives.
- UI components must remain independent of Django models and database operations.
- Accessibility attributes and keyboard interaction must not be removed to achieve visual changes.
- Destructive actions must use appropriate confirmation patterns.
- Forms must provide clear validation and error feedback.
- Reusable UI components must be placed in the shared component structure rather than duplicated inside individual pages.

## Tailwind CSS and Styling

- Use Tailwind CSS for application styling.
- Use the project's defined design tokens instead of arbitrary hardcoded colors.
- Do not introduce raw hexadecimal colors when an existing design token represents the required value.
- Do not introduce arbitrary color values without updating the project's design-token system.
- Maintain consistent spacing, typography, borders, and radius scales.
- Do not name a `--spacing-*` theme key after a display utility (`block`,
  `flex`, `grid`, `inline`, `table`, …). Tailwind turns the key into a utility
  suffix, so `--spacing-block` emits a second `.inline-block` rule that
  overrides the display utility. Use the intended layout word instead
  (`--spacing-stack`).
- Reuse existing utility patterns before creating new styling patterns.
- Do not create inline styles when an existing Tailwind utility or project token provides the required styling.
- Do not create a new visual pattern for a component when an existing project pattern already solves the same problem.
- Responsive behavior must be implemented using the established responsive utilities.
- Dark-mode behavior must follow the application's established theme system.
- Do not hardcode light-mode assumptions into components that must support the system theme.
- Visual changes must not modify business logic, API contracts, permissions, or application state unless explicitly required.

## Django

- Django is the authoritative backend application layer.
- Business rules must be implemented on the backend.
- Django applications must be organized by domain responsibility.
- Do not place unrelated domain logic inside a single Django app.
- Keep views focused on HTTP request/response handling.
- Complex business operations must be implemented in appropriate service/domain modules.
- Models must represent persistent domain state and relationships.
- Do not place large multi-step workflows inside model methods when a dedicated service is more appropriate.
- Do not put presentation-specific logic in models.
- Validate data at the appropriate backend boundary before processing it.
- Database constraints must be used for invariants that the database can enforce.
- Application-level validation must be used for rules requiring business context.
- Do not trust values supplied by the frontend.
- Never use frontend-calculated values as authoritative backend values.
- Use transactions for operations that modify multiple related records and must succeed or fail atomically.
- Do not perform unnecessary database queries inside loops.
- Use appropriate Django ORM techniques such as `select_related` and `prefetch_related` when required to prevent inefficient query patterns.
- Keep database queries close to the domain operation that owns them.
- Do not expose Django model internals directly as an API contract.

## Django REST Framework

- All API endpoints must have a single clear responsibility.
- Validate request data before executing business operations.
- Serializers must validate external API input and output data.
- API views must enforce authentication and authorization before protected operations.
- Object ownership and organizational scope must be verified server-side.
- Never trust an employee ID, application ID, approver ID, or role supplied by the client.
- Use appropriate HTTP status codes consistently.
- API responses must follow consistent project response conventions.
- Do not expose internal exception details to clients.
- Do not return database objects containing fields the requesting user is not authorized to see.
- Keep views thin.
- Complex operations must be delegated to domain/service logic.
- Do not duplicate business rules between serializers and views.
- API endpoints must not bypass workflow validation.
- Mutating endpoints must enforce the appropriate permission checks before performing the mutation.

## Authentication and Authorization

- Authentication must establish the identity of the current user.
- Authorization must determine what that authenticated user is allowed to do.
- Authentication and authorization must never be treated as the same operation.
- Every protected API endpoint must require authentication.
- Every protected operation must perform server-side authorization.
- Users must only access resources within their permitted ownership or organizational scope.
- Employees must only access their own leave applications unless a role explicitly grants broader access.
- Approvers must only access applications within their configured approval scope.
- HR permissions must be enforced independently of frontend visibility.
- Hiding a button or page is not an authorization mechanism.
- Never accept a user role from the frontend as proof of authorization.
- Never infer authorization in the frontend from the account's system role either. Ask the backend what the caller may do (`/api/v1/approvals/capabilities/`) and fail closed when the answer is unavailable.
- Never accept an employee identity from the frontend as proof of ownership.
- Authorization checks must occur before protected mutations.
- Permission failures must not reveal information about resources the user is not authorized to access.

## Leave Domain Logic

- The backend is the single authoritative source for leave calculations.
- Employees must never manually submit the number of leave days as an authoritative value.
- The system must calculate leave days from the submitted start and end dates.
- Weekends must not count as working leave days.
- Configured public holidays must not count as working leave days.
- Leave dates must satisfy the configured notice-period rules.
- Leave applications must not start on the application/submission date.
- Leave applications must not start in the past.
- Leave applications must not cross a financial-year boundary.
- Overlapping leave applications must be rejected according to the established overlap rules.
- Annual leave must be validated against the employee's available annual balance.
- Special leave must not deduct annual leave unless the configured leave type explicitly defines it as annual-leave-consuming.
- Maximum leave duration must be enforced by the backend.
- Leave eligibility rules must be enforced by the backend.
- Supporting-document requirements must be enforced by the backend.
- Changes to leave rules must not silently alter already-submitted applications.

## Leave Balance

- Annual leave balance must be calculated by the system.
- HR must not directly edit an employee's calculated annual leave balance.
- Pending applications must not deduct annual leave.
- Rejected applications must not deduct annual leave.
- Correction-required applications must not deduct annual leave.
- Annual leave must only be deducted after final approval.
- Approved cancellation must restore the applicable annual leave days.
- Canceled approved leave must not become carry-forward leave.
- Carry-forward must be calculated according to the configured financial-year rules.
- Balance calculations must use authoritative database records and configured rules.
- The frontend must never be treated as the source of truth for balance values.

## Approval Workflow

- Approval workflows must be configurable through the backend.
- Workflow stages must execute sequentially.
- Every mandatory configured stage must be completed before the application can progress.
- An approver must never be able to skip a mandatory stage.
- An application must have a valid workflow before submission.
- Every required workflow stage must have a valid responsible approver before the workflow becomes active.
- Approval actions are limited to:
  - Approve
  - Reject
  - Return for Correction
- Approval comments are optional when approving.
- Rejection comments are mandatory.
- Correction comments are mandatory.
- A rejection must stop the current workflow.
- A correction request must return the application to the same approval stage.
- Resubmission after rejection must retain the original reference number.
- Resubmission after correction must retain the original reference number.
- Later approvers must be able to see required previous decisions and comments.
- Existing submitted applications must retain their assigned workflow context.
- Future workflow configuration changes must not silently modify submitted applications.
- HR must not become a normal approval stage unless the configured organizational workflow explicitly defines HR as an approver.

## Server Data Loading

- State a server component needs must be fetched on the server and passed down as props. A client component must not re-fetch, on mount, a fact the server already loaded for the same render.
- Independent reads for one render must be awaited together, not sequentially.
- The current user and the caller's approval capabilities are read by many components per render. Each must be read once per request, not once per component.
- A cache scoped to a request exists to prevent duplicate work within that request. It must not be used to serve data across requests; data that changes must be re-read or explicitly revalidated.

## Application State

- Application state transitions must be controlled by backend domain logic.
- The frontend must never directly determine the next application state.
- Invalid state transitions must be rejected.
- An application must not be simultaneously represented as two mutually exclusive final states.
- A rejected application must not continue through later approval stages.
- A correction-required application must not continue through later approval stages until resubmitted.
- A finally approved application must not be treated as pending.
- A canceled application must not remain an active leave application.
- State changes that affect business records must be auditable.

## API and Data Validation

- Validate all external input at the backend boundary.
- Treat all frontend input as untrusted.
- Validate dates, identifiers, enumerations, file metadata, and configuration values before processing.
- Do not rely exclusively on client-side validation.
- Reject invalid values explicitly.
- Do not silently coerce invalid business data into acceptable values.
- Use database constraints for uniqueness and relational integrity where appropriate.
- Validate business invariants in application logic where database constraints are insufficient.
- Validate authorization before using client-supplied resource identifiers for mutations.

## Database and Data Access

- The relational database is the authoritative source for structured application data.
- Database schema changes must be implemented through Django migrations.
- Never modify the production database schema manually as part of normal development.
- Do not delete or rename persistent fields without considering existing data and migration safety.
- Database transactions must be used for multi-record state changes that must remain consistent.
- Foreign-key relationships must use actual relational constraints.
- Do not duplicate authoritative data unnecessarily.
- Avoid storing derived values when they can become inconsistent with their source unless there is a documented performance reason.
- When derived values are persisted, the code responsible for maintaining them must be explicit and tested.
- Database queries must be optimized for the actual access pattern.
- Do not load entire tables when only a subset of records is required.
- Do not expose database implementation details as frontend contracts.
- A field computed per row must not issue per-row queries. When a list endpoint derives a fact for every row from related tables, read those tables once for the whole result set and join the results in memory.
- Where a fact is exposed twice (for example a boolean and the evidence behind it), both must come from one computation, not two derivations.
- Configured data is expected to grow without a deploy. Query counts for a screen must be a function of what the screen requests, not of how many rows exist; pin that with a query-count test when it matters.

## File Storage

- The production file-storage technology is currently **TBD**.
- File-storage code must be isolated behind a dedicated storage abstraction/service.
- Application business logic must not depend directly on a specific storage provider.
- Database records must contain file metadata and references rather than unnecessary binary file contents.
- Supporting documents must be associated with the correct leave application.
- Users must only access files they are authorized to access.
- File replacement must respect application state rules.
- Approved supporting documents must not be modified by unauthorized users.
- File deletion must not silently destroy required audit or historical records.
- The eventual development storage implementation must be replaceable with the organization's approved storage infrastructure.

## Background Tasks

- Long-running or non-critical asynchronous operations must not unnecessarily block HTTP requests.
- Background processing must use the project's selected task-processing technology once defined.
- Background tasks must be safe to retry where possible.
- Background tasks must not create duplicate business records when retried.
- Critical business state must be persisted before dependent background operations are considered successful.
- Notification failure must not silently change the underlying application decision.
- Background processing must not bypass authorization or business-rule validation.
- Task failures must be logged with enough context to diagnose the failure without exposing sensitive data.

## Notifications

- Email notifications must be triggered by authoritative backend events.
- Notification content must reflect the actual persisted application state.
- The frontend must not send authoritative workflow notifications.
- Notifications must not contain information the recipient is not authorized to receive.
- Failed notification delivery must be recorded.
- Notification failure handling must follow the documented workflow rules.
- Notification logic must not be duplicated across multiple approval endpoints.
- Notification templates must be centralized and reusable.

## Documents

- Generated approved leave documents must be based on the final persisted approved application.
- Documents must never be generated as an authoritative substitute for the database record.
- Document generation must use the approved application state.
- Template customization must modify presentation only.
- Template customization must not modify approved application data.
- Generated documents must contain the correct employee, leave, approval, and balance information.
- Users must only access documents they are authorized to access.
- Document generation failures must be recorded and recoverable.

## Audit and History

- Significant business and administrative actions must be auditable.
- Audit records must identify the actor.
- Audit records must include the action and timestamp.
- Relevant previous and new values must be recorded for state/configuration changes.
- Rejection and correction actions must retain their required reasons/comments.
- Delegation and reassignment actions must retain their relevant reasons and actors.
- Audit history must not be silently deleted as part of normal application operations.
- Historical records must not be rewritten to make past decisions appear different from what actually occurred.
- Audit records must not be exposed to users who are not authorized to see them.

## Configuration and Rules

- Configurable business rules must have one authoritative implementation.
- Do not hard-code values that HR is required to configure.
- The positions an approval stage may name are configuration. Do not switch on a role code, and do not keep a lookup table of role names in either stack; resolve codes against the stored roles and fall back to the stored label for display.
- Current default values must not be duplicated across frontend and backend.
- Configuration changes must have a defined effective point when historical behavior could be affected.
- Existing applications must continue using the rules applicable when they were submitted.
- Future configuration must apply to future applications according to its effective date.
- Invalid workflow or leave-rule configurations must be rejected before activation.
- Configuration changes must be auditable.

## Testing

- Every new business rule must have corresponding backend tests.
- Every important state transition must have tests.
- Authorization boundaries must have tests.
- Ownership restrictions must have tests.
- Leave-day calculations must have tests covering weekends and public holidays.
- Balance calculations must have tests for pending, approved, rejected, corrected, canceled, and special-leave scenarios.
- Workflow tests must verify that mandatory stages cannot be skipped.
- Rejection and correction behavior must be tested independently.
- Resubmission behavior must be tested.
- Configuration changes must be tested for historical integrity.
- API validation and permission failures must be tested.
- Tests must verify both successful and invalid paths.
- A feature is not considered complete if its critical business behavior cannot be verified through automated tests.

## Error Handling

- Errors must be handled at the layer responsible for the failure.
- User-facing errors must be clear and actionable.
- Internal errors must not expose stack traces, secrets, database details, or implementation internals to users.
- Do not catch exceptions merely to suppress them.
- Do not use broad exception handling when a specific exception can be handled.
- Unexpected failures must be logged appropriately.
- Business-rule failures must return predictable API errors.
- Failed operations must not leave partially updated business state when the operation is required to be atomic.

## Logging

- Logs must contain enough context to diagnose failures.
- Do not log passwords, authentication tokens, secrets, or sensitive document contents.
- Do not log unnecessary personal information.
- Log important workflow failures and administrative operations.
- Log background-task failures with relevant identifiers.
- Use appropriate log levels.
- Do not use `print()` for application logging.
- Development debugging statements must be removed before code is considered complete.

## File Organization

The project must maintain clear responsibility boundaries.

### Frontend

```text
frontend/
├── app/
│   └── Application routes and page composition
│
├── components/
│   └── Reusable UI components
│
├── lib/
│   └── Frontend utilities, API clients, and shared helpers
│
└── ...
````

Rules:

* `app/` owns route/page composition.
* `components/` owns reusable UI composition.
* `lib/` owns shared frontend infrastructure and utilities.
* Business rules must not be placed in `components/`.
* API communication must be centralized where practical.
* Do not duplicate the same reusable component across multiple pages.

### Backend

```text
backend/
├── config/
│   └── Django project configuration
│
├── users/
│   └── User and employee identity/domain logic
│
├── leave/
│   └── Leave applications, leave types, balances, and leave rules
│
├── workflows/
│   └── Approval workflow configuration and processing
│
├── notifications/
│   └── Email notification logic
│
├── documents/
│   └── Approved leave document generation
│
├── audit/
│   └── Audit and history functionality
│
└── ...
```

Rules:

* Each Django app must own a clearly defined domain.
* Do not place unrelated business logic in `config/`.
* Do not place business logic in API routing files.
* Shared domain operations must have one authoritative implementation.
* New Django apps must represent a meaningful domain responsibility rather than arbitrary technical grouping.

## Git and Collaboration

These rules apply equally to every developer and coding agent contributing to the project.

* Never commit directly to another developer's feature branch.
* Every feature or bug fix must be developed on an appropriately named branch.
* Do not rewrite another developer's branch history without explicit agreement.
* Do not force-push shared branches.
* Keep commits focused on one logical change.
* Do not combine unrelated features or fixes in one commit.
* Commit messages must clearly describe the change.
* Before opening a pull request, verify that the branch builds and tests successfully.
* Pull requests must describe what changed and why.
* Pull requests must identify important business-rule or architecture changes.
* Do not merge code that violates this document.
* Do not resolve merge conflicts by blindly choosing one side; understand the intended behavior first.
* When modifying shared code, preserve behavior that belongs to other completed features.
* Documentation must be updated when a permanent architecture, business-rule, API, workflow, or implementation decision changes.
* AI-generated code is subject to exactly the same review, testing, security, and standards requirements as human-written code.
* An AI coding agent must not introduce changes outside the requested scope without explicit approval.
* Agents must inspect the existing implementation before modifying shared functionality.
* Agents must not assume that a missing feature means the supporting architecture does not already exist.
* Agents must reuse existing project patterns instead of creating parallel patterns.
* Agents must report unresolved assumptions rather than silently inventing requirements.

## Definition of Code-Complete

Code is considered complete only when all applicable conditions below are satisfied:

* The implementation follows this `code-standards.md`.
* The implementation respects `architecture.md`.
* The feature works within the existing system boundaries.
* Backend business rules are authoritative.
* Authentication and authorization are enforced.
* Required validation exists.
* Critical business behavior is tested.
* Existing functionality has not been unintentionally broken.
* No unused or debugging code remains.
* No secrets or credentials have been committed.
* Required documentation has been updated.
* The relevant verification commands have been run successfully.
* The change is ready for review by the other project developer.

```


