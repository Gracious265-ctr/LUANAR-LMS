# LUANAR Leave Management System — Build Plan

## 1. Build Strategy

Develop the system as two independent product tracks after a shared foundation:

- **HR Track** — employee administration, leave-rule configuration, workflow administration, delegation, reassignment, document templates, and HR history.
- **Employee + Approver Track** — employee leave applications and the complete approval experience for Supervisor, HOD, Dean, Registrar, and DVC.
- **Integration Track** — connects the two independently developed sides after their core functionality is working.

Each unit must:

1. Produce one visible result.
2. Stay within one primary system boundary.
3. Introduce dependencies only when required.
4. Avoid speculative functionality.
5. Be independently verifiable.
6. Update relevant documentation when a permanent implementation or architectural decision is made.
7. Be completed before dependent work begins.

Both developers may work on different tracks simultaneously. They must agree on shared domain concepts and API contracts before implementing dependent integration points.

---

# 2. Development Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js | Web application, routing, pages, forms, and user interactions |
| UI Components | 21st.dev | Reusable interface components |
| Icons | Lucide React | Interface icons |
| Styling | Tailwind CSS | Styling, responsive layouts, and design tokens |
| Backend | Django | Core application logic and business rules |
| API | Django REST Framework | API consumed by Next.js |
| Database | PostgreSQL | Structured application data |
| Authentication | Django authentication → LUANAR institutional authentication | Development authentication with future institutional integration |
| File Storage | Supabase Storage → LUANAR storage | Supporting documents and generated leave documents |
| Cache / Queue | Redis | Caching and Celery message broker |
| Background Processing | Celery | Asynchronous email, document generation, and other long-running work |
| Email | Google SMTP → LUANAR institutional SMTP | Transactional application notifications |
| Public Holidays | Google Calendar API | Public-holiday calendar data |
| PDF Generation | ReportLab | Official approved leave PDF generation |
| DOCX Generation | python-docx | Additional approved leave document format where required |

### Development infrastructure decisions

- Use Google SMTP during development and testing until LUANAR institutional email infrastructure is available.
- Keep email provider configuration separate from notification and business logic.
- Use Supabase Storage during development only if organizational storage has not yet been identified.
- Keep file storage behind a storage service/abstraction so it can be replaced by LUANAR infrastructure later.
- Do not use Supabase as the application's primary database or business backend.
- Keep PostgreSQL as the authoritative system database.
- Use Redis only for temporary/cache/queue concerns, never as the authoritative source of application data.

---

# 3. Shared Foundation

## Unit 1 — Project Foundation and Development Contract

### What it builds

Establish the minimum shared foundation required by both developers:

- Next.js frontend.
- Django backend.
- Django REST Framework.
- PostgreSQL connection.
- Environment configuration.
- Frontend/backend communication.
- 21st.dev component setup.
- Tailwind CSS and project design tokens.
- Lucide React.
- Basic project structure.
- Development authentication mechanism.
- Redis.
- Celery foundation.
- Test infrastructure.
- Shared API conventions.
- Git collaboration conventions.

### Visible result

A working application shell where the frontend can communicate with Django and authenticated development users can be recognized.

### Dependencies

None.

### Ownership

Both developers must agree on this foundation before splitting into the two tracks.

---

# 4. HR Track

The HR developer owns the following units and handles both frontend and backend work for these units.

## Unit 2 — HR Employee Directory

### What it builds

Create the HR employee-management experience:

- Employee list.
- Employee search and filtering.
- Employee profile.
- Create employee.
- Edit employee information.
- Department/faculty assignment.
- Designation/post.
- Date of appointment.
- Employee category.
- Grade assignment.
- Employee activation/deactivation.

For development/testing, HR is the source of employee records.

### Visible result

An HR employee directory where HR can create and manage employee records.

### Dependencies

- Unit 1.

---

## Unit 3 — HR Grade and Annual Entitlement Configuration

### What it builds

Create HR configuration for:

- Grade ranges.
- Annual entitlement.
- Employee grade assignment.
- Future-effective entitlement changes.

Initial configuration:

- A–C → 21 days.
- D–G → 24 days.
- H–U → 30 days.

The system must determine an employee's entitlement from the configured grade rather than allowing HR to manually edit the employee's balance.

### Visible result

An HR grade and entitlement configuration screen showing how annual leave entitlement is determined.

### Dependencies

- Unit 2.

---

## Unit 4 — HR Leave Type and Rule Management

### What it builds

Allow HR to configure:

- Annual leave.
- Maternity leave.
- Paternity leave.
- Compassionate leave.
- Additional HR-defined leave types.

For each configurable leave type support:

- Maximum duration.
- Eligibility.
- Minimum notice period.
- Supporting-document requirement.
- Whether it consumes annual entitlement.
- Effective dates.

Initial special-leave defaults:

- Maternity → 90 days.
- Paternity → 10 days.

### Visible result

An HR leave-rule management interface.

### Dependencies

- Unit 2.
- Unit 3.

---

## Unit 5 — HR Financial Year and Calendar Configuration

### What it builds

Create HR configuration for:

- Active financial year.
- Financial-year start and end dates.
- Future financial-year periods.
- Public-holiday configuration/integration boundary.

The system must use the configured financial year when validating leave applications.

### Visible result

An HR financial-year/calendar configuration page.

### Dependencies

- Unit 1.
- Unit 2.

---

## Unit 6 — HR Workflow Builder

### What it builds

Create configurable approval workflows based on:

- Employee category.
- Department/faculty.
- Approval stages.
- Stage order.
- Assigned approvers.

Support configured stages such as:

- Supervisor.
- HOD.
- Dean.
- Registrar.
- DVC.

Every configured stage is mandatory and sequential.

### Visible result

An HR workflow configuration interface showing a complete approval sequence.

### Dependencies

- Unit 2.
- Unit 3.
- Unit 4.

---

## Unit 7 — HR Workflow Validation and Scheduling

### What it builds

Add workflow administration capabilities for:

- Required-stage validation.
- Missing approver validation.
- Inactive approver validation.
- Invalid configuration detection.
- Conflicting workflow detection.
- Future-effective workflow scheduling.
- Active/inactive workflow states.

Workflow configuration must be validated before activation or scheduling.

### Visible result

HR can validate and schedule a workflow for a future effective date.

### Dependencies

- Unit 6.

---

## Unit 8 — HR Delegation Management

### What it builds

Create:

- Approver unavailability requests.
- Delegate nomination.
- HR approval.
- HR rejection.
- Mandatory HR decision reason.
- Active delegation management.
- Delegation cancellation.
- Automatic return of unacted applications to the original approver.

### Visible result

An HR delegation-management interface.

### Dependencies

- Unit 6.
- Unit 7.

---

## Unit 9 — HR Emergency Reassignment

### What it builds

Allow HR to:

- View applications requiring intervention.
- Reassign pending applications.
- Select replacement approvers.
- Record a mandatory reassignment reason.
- Notify affected users.
- Preserve reassignment history.

Employee-facing views must expose the new responsible approver but not the internal HR reason.

### Visible result

An HR intervention interface for reassigning an active application.

### Dependencies

- Unit 6.
- Unit 8.

---

## Unit 10 — HR Approved Leave Document Template

### What it builds

Create HR's official leave-document template management:

- Official template.
- Logo/branding.
- Official wording.
- Fields.
- Signature areas.
- Layout configuration.
- Template preview.
- Template update.

HR may customize the template but must not alter actual approved application data through the template system.

### Visible result

An HR interface for managing the official approved-leave document template.

### Dependencies

- Unit 2.
- Unit 4.

---

## Unit 11 — HR Finalized Leave and Audit View

### What it builds

Create HR's organization-level administrative view for:

- Approved applications.
- Rejected applications.
- Application history.
- Approval decisions.
- Rejection reasons.
- Correction history.
- Resubmissions.
- Cancellations.
- Delegations.
- Reassignments.
- Rule changes.
- Entitlement changes.
- Workflow changes.
- Document replacement history.

Normal HR visibility should focus on finalized records and administrative intervention rather than making HR a normal approval stage.

### Visible result

An HR administrative history/audit interface.

### Dependencies

- Units 2–10.

---

# 5. Employee + Approver Track

The Employee + Approver developer owns the following units and handles both frontend and backend work for these units.

Development fixtures may be used where HR-managed data does not yet exist.



---

## Unit 13 — Leave Application and Drafts

### What it builds

Create the complete application creation experience:

- New application.
- Multiple drafts.
- Leave type selection.
- Start date.
- End date.
- Reason.
- Supporting documents.
- Save draft.
- Edit draft.
- Delete draft.
- Review before submission.

The employee must not manually enter the number of leave days.

### Visible result

A working employee leave-application form with draft and review functionality.

### Dependencies

- Unit 1.
- Leave-type API contract from Unit 4.
- Calendar/rule API contract from Unit 5.

---

## Unit 14 — Leave Validation and Submission

### What it builds

Implement authoritative leave-submission validation:

- Working-day calculation.
- Weekend exclusion.
- Public-holiday exclusion.
- Minimum notice period.
- Maximum duration.
- Eligibility.
- Financial-year boundary.
- Available-balance validation.
- Overlap detection.
- Required-document validation.
- Unique reference-number generation.
- Submission confirmation.

Rules:

- Start date must be a future working day.
- Leave cannot start on the submission date.
- Leave cannot cross financial-year boundaries.
- Pending applications do not deduct annual leave.
- Rejected applications do not deduct annual leave.
- Annual leave is deducted only after final approval.
- Special leave does not deduct annual entitlement where configured as non-annual leave.

### Visible result

An employee can submit a valid leave application and receive a unique reference number.

### Dependencies

- Unit 13.
- Leave rules from Unit 4.
- Financial-year/calendar rules from Unit 5.
- Employee/grade information from Units 2–3.

---

## Unit 15 — Employee Application Tracking

### What it builds

Create an application tracker showing:

- Reference number.
- Current status.
- Approval stages.
- Current stage.
- Current responsible approver.
- Approver role.
- Decision date/time.
- Previous decisions.
- Previous comments.
- Rejection details.
- Correction details.
- Resubmission state.

### Visible result

An employee tracking page showing exactly where a submitted application is in the workflow.

### Dependencies

- Unit 14.
- Workflow contract from Unit 6.

---

## Unit 16 — Approver Review and Decision

### What it builds

Create the complete approval experience for:

- Supervisor.
- HOD.
- Dean.
- Registrar.
- DVC.

Include:

- Assigned applications.
- Application details.
- Permitted employee information.
- Permitted leave history.
- Current balance.
- Supporting documents.
- Previous decisions/comments.
- Approve.
- Reject.
- Return for correction.

Enforce:

- Approval comment is optional.
- Rejection comment is mandatory.
- Correction comment is mandatory.
- Stages are sequential.
- Approvers can act only on applications currently assigned to them.

### Visible result

An approver dashboard where the responsible approver can review and decide on an application.

### Dependencies

- Unit 14.
- Unit 15.
- Workflow configuration contract from Unit 6.

---

## Unit 17 — Rejection, Correction, and Resubmission

### What it builds

Implement:

- Rejected state.
- Rejection reason.
- Employee editing after rejection.
- Correction-required state.
- Correction comment.
- Employee editing after correction.
- Resubmission.
- Stable reference number.
- Return to the rejecting/correcting approver.
- Change visibility for the approver.

### Visible result

A complete reject → edit → resubmit and correction → edit → resubmit experience.

### Dependencies

- Unit 16.

---

## Unit 18 — Leave Cancellation

### What it builds

Create:

- Employee cancellation request.
- Cancellation reason.
- Cancellation confirmation.
- Cancellation approval workflow.
- Cancellation decision.
- Employee notification state.
- Approved-leave cancellation before leave start.
- Balance restoration after approved cancellation.

Rules:

- Pending applications can be cancelled by the employee before final approval.
- Approved leave can be cancelled before its start date.
- Cancellation requires a reason.
- Approved annual leave cancellation restores applicable deducted days.
- Cancelled approved leave does not become carry-forward.

### Visible result

An employee/approver cancellation workflow.

### Dependencies

- Unit 16.
- Unit 14.
- Balance logic from Unit 14.

---

## Unit 19 — Supporting Document Lifecycle

### What it builds

Complete document handling:

- Upload.
- View.
- Download.
- Required-document validation.
- Replacement during draft.
- Replacement after rejection.
- Replacement after correction.
- Read-only documents while under review.
- Read-only documents after approval.
- Document replacement history.

### Visible result

A complete supporting-document experience attached to a leave application.

### Dependencies

- Unit 13.
- File-storage abstraction from Unit 1.
- Development storage implementation.

---

# 6. Integration Track

Begin these units only after the relevant HR and Employee + Approver units are independently functional.

## Unit 20 — HR-to-Employee Data Integration

### What it builds

Connect HR-managed employee data to the employee experience:

```text
HR creates employee
        ↓
HR assigns grade
        ↓
HR assigns department/category
        ↓
System resolves entitlement
        ↓
Employee logs in
        ↓
Employee sees correct profile
        ↓
Employee sees correct entitlement and balance
```

Replace development fixtures with real HR-managed records.

### Visible result

The employee dashboard reflects the actual employee record configured by HR.

### Dependencies

- HR Units 2–5.
- Employee Units 12–14.

---

## Unit 21 — Workflow-to-Approver Integration

### What it builds

Connect HR workflow configuration to real submitted applications:

```text
HR configures workflow
        ↓
Employee submits application
        ↓
System resolves applicable workflow
        ↓
Correct approver receives application
        ↓
Approver acts
        ↓
Next configured stage receives application
```

Remove hard-coded development workflows.

Verify:

- Employee category routing.
- Department/faculty routing.
- Mandatory stages.
- Sequential progression.
- Correct responsible approver.
- Delegated approvers.
- Reassigned applications.

### Visible result

A real submitted application automatically follows the workflow configured by HR.

### Dependencies

- HR Units 6–9.
- Employee/Approver Units 14–17.

---

## Unit 22 — Email Notifications

### What it builds

Connect system events to **Google SMTP** for development and testing.

Implement notifications for:

- Application submission.
- Approval-stage assignment.
- Approval.
- Rejection.
- Correction request.
- Resubmission.
- Reassignment.
- Delegation events.
- Cancellation request.
- Cancellation decision.
- Final approval.

Implement:

- Centralized notification/email service.
- Reusable email templates.
- Configurable sender address.
- SMTP credentials through environment variables.
- Delivery failure logging.
- HR/administration notification for required delivery failures.

Google SMTP must be replaceable with LUANAR institutional SMTP through configuration.

### Visible result

A real leave application triggers the appropriate email notifications.

### Dependencies

- Units 14–18.
- HR Units 8–9.
- Redis/Celery from Unit 1.

---

## Unit 23 — Final Approval, Balance, and Document Generation

### What it builds

Connect final approval to:

```text
Final approval
      ↓
Balance update
      ↓
Approved application
      ↓
Document generation
      ↓
PDF
      ↓
Authorized access
```

Implement:

- Automatic annual leave deduction.
- Special-leave balance behavior.
- Final balance calculation.
- Approved document generation.
- Template population.
- PDF output.
- Additional document format where required.
- Authorized document access.

### Visible result

A fully approved leave application produces an official approved leave document and the employee's balance is updated.

### Dependencies

- Unit 10.
- Unit 14.
- Unit 16.
- Unit 19.
- Unit 20.
- Unit 21.
- ReportLab/python-docx setup as required.

---

## Unit 24 — Complete Audit and Historical Integrity

### What it builds

Connect all significant operations into the authoritative audit trail:

- Submission.
- Approval.
- Rejection.
- Correction.
- Resubmission.
- Cancellation.
- Delegation.
- Reassignment.
- Rule changes.
- Entitlement changes.
- Workflow changes.
- Document replacement.

Verify that submitted applications preserve the rules and workflow context that existed when they were submitted.

Historical records must not silently change because HR later modifies:

- Leave rules.
- Entitlements.
- Workflow configuration.
- Approver assignments.

### Visible result

A complete application history/audit trail that reconstructs what happened to an application.

### Dependencies

- Unit 11.
- Unit 17.
- Unit 18.
- Unit 19.
- Unit 21.
- Unit 22.
- Unit 23.

---

## Unit 25 — End-to-End System

### What it builds

Verify and finish the complete LUANAR leave-management workflow:

```text
HR creates employee
        ↓
HR assigns grade
        ↓
HR configures leave rules
        ↓
HR configures workflow
        ↓
Employee logs in
        ↓
Employee creates application
        ↓
System validates application
        ↓
Reference number generated
        ↓
Supervisor receives application
        ↓
Supervisor approves
        ↓
Next configured approver receives application
        ↓
All mandatory stages approve
        ↓
Final approver approves
        ↓
Annual balance updated
        ↓
Approved document generated
        ↓
Emails sent
        ↓
Employee views approved leave
        ↓
HR sees finalized record
```

Also verify:

```text
Rejection
Correction
Resubmission
Cancellation
Delegation
Reassignment
```

### Visible result

A complete working LUANAR leave-management system from HR configuration through employee application, approval, notification, balance update, document generation, and history.

### Dependencies

- Units 1–24.

---

# 7. Parallel Development Plan

After Unit 1, development can proceed in parallel:

```text
                         UNIT 1
                    Shared Foundation
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       HR DEVELOPER                EMPLOYEE + APPROVER
             │                           │
             ▼                           ▼
          Unit 2                       Unit 12
          Unit 3                       Unit 13
          Unit 4                       Unit 14
          Unit 5                       Unit 15
          Unit 6                       Unit 16
          Unit 7                       Unit 17
          Unit 8                       Unit 18
          Unit 9                       Unit 19
          Unit 10
          Unit 11
             │                           │
             └─────────────┬─────────────┘
                           ▼
                     INTEGRATION
                           │
                        Unit 20
                        Unit 21
                        Unit 22
                        Unit 23
                        Unit 24
                        Unit 25
```

## Collaboration Rule

Each developer owns the complete vertical slice for their assigned track.

Do not divide a unit into:

```text
Developer A → frontend
Developer B → backend
```

Instead:

```text
Developer A → HR feature
                ├── HR frontend
                ├── HR API
                ├── HR business logic
                ├── HR database changes
                └── HR tests

Developer B → Employee/Approver feature
                ├── frontend
                ├── API
                ├── business logic
                ├── database changes
                └── tests
```

The ownership boundary is based on **business responsibility**, not technology.

---

# 8. Shared API Contract Rule

Before parallel work begins on a feature that crosses tracks, agree on its contract.

For example, the Employee + Approver developer may initially work against development fixtures for:

```text
GET /api/v1/employees/me/
GET /api/v1/leave-types/
GET /api/v1/workflows/current/
POST /api/v1/leave-applications/
GET /api/v1/leave-applications/{id}/
```

The exact endpoints must be documented and agreed upon before implementation.

The Employee + Approver side must not invent a separate employee model simply because the HR side has not yet completed its implementation.

The HR side must not unexpectedly change an agreed API contract without coordinating the change.

---

# 9. Just-in-Time Dependency Rules

Do not install or implement infrastructure merely because it might be needed later.

Examples:

- Do not add Google SMTP configuration before Unit 22.
- Do not build document-generation infrastructure before Unit 23.
- Do not implement public-holiday integration before leave-date validation requires it.
- Do not build delegation infrastructure before Unit 8.
- Do not build reassignment infrastructure before Unit 9.
- Do not build the final audit aggregation before the underlying actions exist.
- Do not build LUANAR institutional authentication before the required institutional integration details are known.
- Do not replace development authentication until LUANAR authentication requirements are confirmed.
- Do not finalize organizational file storage until LUANAR storage infrastructure is investigated.

---

# 10. Integration Rules

Do not prematurely couple the HR and Employee + Approver tracks.

The tracks may share:

- PostgreSQL.
- Django project infrastructure.
- Authentication identity.
- Core domain identifiers.
- API conventions.
- Shared configuration.
- Shared audit mechanisms.

The following must remain configurable rather than hard-coded:

- Employee grade entitlements.
- Leave types.
- Maximum durations.
- Eligibility.
- Supporting-document requirements.
- Minimum notice periods.
- Financial years.
- Approval workflows.
- Approvers.
- Future-effective configurations.

---

# 11. End-to-End Definition of Done

The project is not complete until the following workflow succeeds:

```text
1. HR creates an employee.
2. HR assigns department/category.
3. HR assigns grade.
4. System determines annual entitlement.
5. HR configures applicable leave rules.
6. HR configures the applicable approval workflow.
7. Employee authenticates.
8. Employee sees correct profile and balance.
9. Employee creates a leave application.
10. Employee can save it as a draft.
11. Employee reviews the application.
12. System validates dates, working days, holidays, notice period,
    eligibility, duration, balance, documents, overlap, and financial year.
13. System generates a unique reference number on submission.
14. The application is automatically assigned to the first approver.
15. The approver can approve, reject, or return for correction.
16. The application moves sequentially through all configured stages.
17. Later approvers can see relevant previous decisions and comments.
18. Rejection stops the workflow without deducting leave.
19. Correction allows editing and resubmission to the same stage.
20. Resubmission keeps the same reference number.
21. Final approval deducts applicable annual leave.
22. Special leave follows its configured balance rules.
23. Approved leave generates the official document.
24. Required users receive email notifications.
25. Employee can access the approved leave document.
26. HR can access the finalized record.
27. Cancellation follows the configured cancellation process.
28. Approved cancellation restores applicable annual leave.
29. Delegation transfers unacted work correctly.
30. Delegation completion returns unacted applications to the original approver.
31. HR can perform emergency reassignment.
32. All significant actions are recorded in the audit history.
33. Historical applications retain the rules and workflow that applied
    when they were submitted.
```

---

# 12. Final Unit Dependency Map

| Unit | Name | Track | Depends On |
|---:|---|---|---|
| 1 | Project Foundation and Development Contract | Shared | None |
| 2 | HR Employee Directory | HR | 1 |
| 3 | HR Grade and Annual Entitlement Configuration | HR | 2 |
| 4 | HR Leave Type and Rule Management | HR | 2, 3 |
| 5 | HR Financial Year and Calendar Configuration | HR | 1, 2 |
| 6 | HR Workflow Builder | HR | 2, 3, 4 |
| 7 | HR Workflow Validation and Scheduling | HR | 6 |
| 8 | HR Delegation Management | HR | 6, 7 |
| 9 | HR Emergency Reassignment | HR | 6, 8 |
| 10 | HR Approved Leave Document Template | HR | 2, 4 |
| 11 | HR Finalized Leave and Audit View | HR | 2–10 |
| 12 | Employee Profile and Leave Dashboard | Employee + Approver | 1, Unit 2 contract |
| 13 | Leave Application and Drafts | Employee + Approver | 1, Unit 4 contract, Unit 5 contract |
| 14 | Leave Validation and Submission | Employee + Approver | 13, Units 2–5 contracts |
| 15 | Employee Application Tracking | Employee + Approver | 14, Unit 6 contract |
| 16 | Approver Review and Decision | Employee + Approver | 14, 15, Unit 6 contract |
| 17 | Rejection, Correction, and Resubmission | Employee + Approver | 16 |
| 18 | Leave Cancellation | Employee + Approver | 14, 16 |
| 19 | Supporting Document Lifecycle | Employee + Approver | 13, 1 |
| 20 | HR-to-Employee Data Integration | Integration | HR 2–5, Employee 12–14 |
| 21 | Workflow-to-Approver Integration | Integration | HR 6–9, Employee 14–17 |
| 22 | Email Notifications | Integration | 14–18, 8–9 |
| 23 | Final Approval, Balance, and Document Generation | Integration | 10, 14, 16, 19–21 |
| 24 | Complete Audit and Historical Integrity | Integration | 11, 17–19, 21–23 |
| 25 | End-to-End System | Integration | 1–24 |

---

# 13. Ownership Summary

| Area | HR Developer | Employee + Approver Developer |
|---|---|---|
| Employee management | Primary | Uses |
| Grade management | Primary | Uses |
| Entitlement configuration | Primary | Uses |
| Leave-rule configuration | Primary | Uses |
| Financial-year configuration | Primary | Uses |
| Workflow configuration | Primary | Uses |
| Delegation | Primary | Approver request/interaction |
| Emergency reassignment | Primary | Receives assignment |
| Employee dashboard | Uses data | Primary |
| Leave application | Uses data | Primary |
| Drafts | — | Primary |
| Leave validation | Provides rules | Primary application experience |
| Approval | Configuration | Primary |
| Rejection/correction | — | Primary |
| Cancellation | Administrative support | Primary employee/approver experience |
| Supporting documents | Administrative access | Primary application experience |
| Document template | Primary | Uses generated document |
| Email notifications | Configuration/intervention | Receives notifications |
| Final document | Template ownership | Employee/approver access |
| Audit | HR visibility | Application history |
| Integration | Joint | Joint |
