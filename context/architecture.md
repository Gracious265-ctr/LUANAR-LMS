
````markdown
# Architecture — LUANAR Leave Management System

## 1. Architecture Overview

The LUANAR Leave Management System is a web-based application that separates the user interface, application/business logic, authentication, and data persistence into clear layers. The frontend is responsible for presenting the system and collecting user input, while the Django backend owns business rules, workflow processing, authorization, and database access. File storage is intentionally left undefined until the organization’s existing storage infrastructure is investigated so that development and testing can use an architecture compatible with the eventual LUANAR environment.

The system should be designed so that organization-specific infrastructure can be introduced later without requiring major changes to the core leave-management logic.

---

## 2. Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js | Web application, routing, pages, forms, and user-facing interactions |
| UI Components | 21st.Dev | Reusable interface components and consistent UI patterns |
| Styling | Tailwind CSS | Frontend styling and responsive layouts |
| Backend | Django | Core application logic, business rules, workflow processing, and server-side operations |
| API | Django REST Framework | Provides API endpoints consumed by the Next.js frontend |
| Database | PostgreSQL | Stores structured application data, users, leave applications, workflows, approvals, configuration, and audit records |
| Authentication | Django authentication / LUANAR institutional authentication* | Authenticates users and establishes their system identity |
| File Storage | supabase | Stores supporting documents and generated approved leave documents; organization infrastructure must be investigated before final selection |
| Cache | redis | Temporary caching and performance-related data if required |
| Background Processing | celery | Handles operations that should not block normal web requests, such as document generation or email processing |
| Email | smtp | Sends application, approval, rejection, correction, delegation, cancellation, and final-approval notifications |

\* Final technologies that depend on LUANAR's existing infrastructure must be confirmed before production deployment.

---

## 3. System Structure

The project should maintain a clear separation between frontend presentation and backend application responsibilities.

A high-level structure is:

```text
luanar-leave-system/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
│
├── backend/
│   ├── config/
│   ├── users/
│   ├── leave/
│   ├── workflows/
│   ├── notifications/
│   ├── documents/
│   ├── audit/
│   └── ...
│
├── storage/
│   └── TBD
│
└── docs/
    └── ...
````

The exact Django app names may change during implementation, but the responsibility boundaries must remain clear.

---

## 4. System Boundaries

### 4.1 Frontend — `/frontend`

The frontend owns the presentation layer and user interaction.

Responsibilities:

* Display dashboards and application information.
* Provide leave application forms.
* Display employee leave balances.
* Display application status and workflow progress.
* Display approval interfaces for authorized approvers.
* Display HR administration interfaces.
* Perform basic client-side validation for user experience.
* Send requests to the Django API.
* Display API validation and business-rule errors.
* Handle authenticated user sessions from the perspective of the UI.

The frontend must **not** own authoritative business rules.

For example, the frontend may display that an annual leave application requires available balance, but the backend must perform the authoritative balance validation.

The frontend must not:

* Decide whether an application can be approved.
* Calculate authoritative leave balances.
* Decide which user is an approver.
* Assign workflow stages.
* Modify database records directly.
* Bypass backend authorization.

---

### 4.2 Backend — `/backend`

The Django backend owns the application's authoritative behavior.

Responsibilities:

* Authentication and user identity handling.
* Authorization and role enforcement.
* Employee records.
* Leave applications.
* Leave-type configuration.
* Leave entitlement rules.
* Leave balance calculations.
* Working-day calculations.
* Public-holiday validation.
* Financial-year rules.
* Application overlap validation.
* Approval workflows.
* Approval decisions.
* Rejection and correction handling.
* Resubmission processing.
* Cancellation processing.
* Delegation and reassignment.
* Notification triggering.
* Document generation coordination.
* Audit logging.
* Database access.
* API validation.

All authoritative business decisions must originate from the backend.

---

### 4.3 File Storage — `/storage`

File storage is intentionally **TBD**.

The system will eventually need storage for:

* Supporting documents uploaded with leave applications.
* Generated approved leave documents.
* Potential document versions/history where required.

The storage technology and infrastructure must not be assumed until LUANAR's existing storage environment is investigated.

The final implementation should isolate file-storage operations behind a dedicated service or abstraction so that the underlying storage mechanism can be changed without changing leave-application logic.

---

### 4.4 Cache

Caching is not currently assigned a specific technology.

If caching is required, it must contain temporary or reproducible information rather than authoritative business records.

The database remains the source of truth for leave applications, balances, approvals, workflow configuration, and audit history.

---

## 5. Storage Model

The system separates persistent structured data, files, and temporary cached information.

### 5.1 Database

The database stores structured and authoritative system information.

Examples:

| Data                                    | Storage  |
| --------------------------------------- | -------- |
| Employee records                        | Database |
| Employee roles                          | Database |
| Employee grades                         | Database |
| Grade entitlement configuration         | Database |
| Leave applications                      | Database |
| Leave types                             | Database |
| Leave-type rules                        | Database |
| Leave dates                             | Database |
| Calculated application days             | Database |
| Leave balances/history                  | Database |
| Workflow definitions                    | Database |
| Workflow stages                         | Database |
| Assigned approvers                      | Database |
| Approval decisions                      | Database |
| Approval comments                       | Database |
| Rejection reasons                       | Database |
| Correction requests                     | Database |
| Delegations                             | Database |
| Reassignments                           | Database |
| Cancellation requests/decisions         | Database |
| Financial-year configuration            | Database |
| Public-holiday references/configuration | Database |
| Notification records/status             | Database |
| Audit records                           | Database |
| Document metadata                       | Database |

The database must remain the authoritative source for system state.

---

### 5.2 File Storage

The eventual file-storage system will contain binary documents rather than application state.

Examples:

* Supporting documents.
* Approved leave PDFs.
* Other generated document formats.
* Document versions where required.

The database should store metadata and references to files rather than unnecessarily storing large binary files inside ordinary application records.

The exact storage implementation is **TBD pending LUANAR infrastructure investigation**.

---

### 5.3 Cache

Cache is reserved for temporary, performance-oriented information.

Possible examples include:

* Frequently accessed configuration.
* Short-lived session-related information.
* Temporary computation results.
* Rate-limiting data.
* Temporary background-job state.

Cached data must be safe to recreate from authoritative sources.

A cache failure must not cause permanent loss of leave applications, approval decisions, balances, or audit history.

---

## 6. Authentication and Access Model

### 6.1 Authentication

The system is intended to use existing LUANAR institutional accounts.

The exact institutional identity provider and integration mechanism are **TBD** and must be confirmed with LUANAR IT.

The architecture should therefore separate:

```text
Institutional Identity
        ↓
Authentication
        ↓
Application User
        ↓
System Role
        ↓
Permissions
```

This allows the application's internal authorization model to remain stable even if the institutional authentication mechanism changes.

---

### 6.2 User Ownership

Each leave application belongs to the employee who submitted it.

The employee's identity must be determined by the authenticated backend user rather than supplied as trusted information by the frontend.

For example:

```text
Authenticated User
        ↓
Employee Record
        ↓
Leave Application
        ↓
Application Owner
```

An employee must not be able to submit an application on behalf of another employee by changing an employee ID in a frontend request.

---

### 6.3 Role-Based Access

Access is controlled by the user's assigned system role and organizational scope.

Primary roles include:

* Employee
* Supervisor
* HOD
* Dean
* Registrar
* DVC
* HR

Permissions must be enforced by the backend.

Examples:

| Role       | Access Principle                                                                  |
| ---------- | --------------------------------------------------------------------------------- |
| Employee   | Own applications and personal leave information                                   |
| Supervisor | Applications assigned to the supervisor and permitted employee information        |
| HOD        | Applications within the HOD's department                                          |
| Dean       | Applications within the applicable academic/faculty scope                         |
| Registrar  | Applications within the Registrar's authorized scope                              |
| DVC        | Applications reaching the configured DVC stage                                    |
| HR         | Organization-wide administrative/configuration access according to HR permissions |

The frontend may hide unavailable actions for usability, but hiding a UI element is **not** an authorization mechanism.

The backend must independently verify every protected operation.

---

## 7. Leave and Workflow Processing

The backend owns the leave-management state machine.

A simplified application lifecycle is:

```text
Draft
  ↓
Submitted
  ↓
Pending Approver
  ↓
Approve ─────────→ Next Stage
  │
  ├── Reject ────→ Rejected
  │
  └── Correction → Correction Required
                         ↓
                    Employee Resubmits
                         ↓
                    Same Approver
```

After the final configured approval:

```text
Final Approval
      ↓
Approved
      ↓
Balance Updated
      ↓
Approved Document Generated
      ↓
Notifications Sent
```

The actual approval stages are determined by the employee's configured workflow.

The workflow must not be hard-coded around a single sequence such as:

```text
Supervisor → HOD → Registrar → DVC
```

Different employee categories may use different configured workflows.

---

## 8. Background Processing

The system may require background processing for operations that are slow or should not block an HTTP request.

Potential background operations include:

* Sending email notifications.
* Generating approved leave documents.
* Processing uploaded supporting documents.
* Synchronizing public-holiday information.
* Other integrations introduced during implementation.

The background-processing technology is currently **TBD**.

Background jobs must not become the authoritative source of business state. Important state transitions must be persisted in the database.

For example, an approval must be recorded as an approval in the database before notification delivery is treated as a secondary operation.

---

## 9. AI Model

The LUANAR Leave Management System does **not currently require an AI model** for its core functionality.

Leave approval decisions, balance calculations, eligibility checks, workflow routing, and authorization must be deterministic system operations.

AI should not be introduced into core decision-making unless a future requirement explicitly justifies it.

---

## 10. Configuration Model

Rules that may change over time should be represented as configurable data rather than hard-coded application logic where practical.

Examples include:

* Annual leave entitlement by grade range.
* Leave types.
* Maximum leave duration.
* Eligibility rules.
* Minimum notice periods.
* Supporting-document requirements.
* Approval workflows.
* Financial-year dates.
* Public-holiday configuration.
* Future-effective configuration changes.

Configuration changes must have an effective date where historical behavior could otherwise be affected.

---

## 11. Historical Integrity

Once a leave application is submitted, the system must preserve the rules and workflow context that applied to that application.

A later configuration change must not silently rewrite historical applications.

For example:

```text
Workflow A
    ↓
Application submitted
    ↓
Application retains Workflow A
    ↓
HR activates Workflow B
    ↓
New applications use Workflow B
```

Existing applications continue using their assigned workflow unless an explicit administrative reassignment operation occurs.

The same principle applies to leave-type rules and other configuration that affects an application's processing.

---

# 12. Invariants

The following rules must never be violated by the codebase.

### 12.1 Backend Authority

**All authoritative business rules must be enforced by the backend.**

The frontend must never be trusted to determine:

* Leave eligibility.
* Available balance.
* Approval permissions.
* Workflow routing.
* Application ownership.
* Final application state.

---

### 12.2 Application Ownership

**An employee can only create, view, modify, or cancel their own applications unless an explicitly authorized administrative or approval role permits the operation.**

The employee identity must come from the authenticated backend identity, not from an untrusted employee identifier supplied by the client.

---

### 12.3 Sequential Workflow

**A leave application must never skip a mandatory configured approval stage.**

An application can move to the next stage only after the current stage has completed its required action.

---

### 12.4 Balance Integrity

**Pending, rejected, or correction-required annual leave applications must never permanently deduct annual leave balance.**

Annual leave is deducted only after final approval.

Approved cancellation must restore the applicable deducted annual-leave days.

---

### 12.5 Historical Integrity

**Changes to current configuration must never silently modify the rules, workflow, decisions, or historical state of an already-submitted application.**

Historical applications must retain the applicable processing context.

---

### 12.6 Authorization Integrity

**Every protected backend operation must verify the authenticated user's role and organizational scope.**

A user must never gain access merely because the frontend displays or submits an identifier belonging to another user.

---

### 12.7 Workflow Integrity

**An application must always have a valid configured workflow before submission.**

The system must not submit an application into an incomplete workflow with missing mandatory stages or unavailable required approvers.

---

### 12.8 Document Integrity

**An approved leave document must represent the approved application data and must not be editable through document-template customization.**

Template customization changes presentation, not the underlying approved leave record.

---

### 12.9 Cache Independence

**Loss or invalidation of cached data must never cause loss of authoritative leave-management data.**

Applications, approvals, balances, workflow decisions, and audit records must remain recoverable from persistent storage.

---

### 12.10 Audit Integrity

**Significant workflow, administrative, and decision-making actions must produce an auditable record.**

The audit record must identify the actor, action, timestamp, and relevant previous/new state or reason where applicable.

---

## 13. Architecture Decisions Still To Be Confirmed

The following decisions are intentionally left open until the relevant LUANAR infrastructure and organizational requirements are investigated:

| Decision                                 | Status |
| ---------------------------------------- | ------ |
| Production file-storage technology       | TBD    |
| Development/test file-storage equivalent | TBD    |
| Production database infrastructure       | TBD    |
| Institutional identity provider          | TBD    |
| Employee-data source/integration         | TBD    |
| Cache technology                         | TBD    |
| Background-job technology                | TBD    |
| Email provider/institutional mail system | TBD    |
| Public-holiday data source and fallback  | TBD    |
| Personal-file/document integration       | TBD    |
| Exact deployment infrastructure          | TBD    |

These decisions should be added to this document once confirmed. They should not be assumed during implementation merely to fill architectural gaps.

```
```

