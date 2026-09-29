# LUANAR Leave Management System — Project Overview

## Overview

The **LUANAR Leave Management System** is a web-based application that digitizes and modernizes Lilongwe University of Agriculture and Natural Resources (LUANAR)'s paper-based leave application and approval process. Employees use their existing LUANAR institutional accounts to submit leave applications by selecting a leave type and future dates, while the system automatically calculates working days, validates leave rules and balances, and routes applications through the configured approval workflow. Supervisors, HODs, Deans, Registrars, and other configured approvers review applications sequentially and can approve, reject, or return them for correction. HR manages employee records, grade-based entitlements, leave-type rules, approval workflows, delegation, and the official leave-document template, while the system handles balance calculations, notifications, audit history, and approved-document generation automatically. The system modernizes the process without reproducing legacy paper-form fields that do not provide meaningful value in a digital workflow.

## Goals

1. **Digitize the leave application process**

   * Replace paper-based leave applications with an electronic application workflow.
   * Allow employees to submit applications without manually reproducing information already maintained in their employee profile.

2. **Automate leave calculations**

   * Calculate working days from the selected start and end dates.
   * Exclude weekends and configured public holidays.
   * Automatically calculate annual leave balances.
   * Prevent invalid leave requests from being submitted.

3. **Automate approval routing**

   * Automatically send submitted applications to the first configured approver.
   * Process mandatory approval stages sequentially.
   * Support different workflows based on employee category and department/faculty.

4. **Give employees clear visibility**

   * Show current leave entitlement and available balance.
   * Show application status and approval progress.
   * Show the current responsible approver.
   * Provide rejection and correction information.
   * Provide access to finalized approved leave documents.

5. **Give approvers the information required to make decisions**

   * Show application details, supporting documents, current balance, and relevant leave history.
   * Show decisions and comments made by previous approval stages.
   * Allow approvers to approve, reject, or return applications for correction.

6. **Make HR the administrator of rules rather than individual balances**

   * Allow HR to configure grade-based annual entitlements.
   * Allow HR to configure leave types and their rules.
   * Allow HR to configure approval workflows.
   * Allow HR to define the approver positions those workflows name, and to staff them per team or institution-wide, without a code change.
   * Prevent HR from manually editing an individual employee's calculated leave balance.

7. **Handle operational exceptions**

   * Allow approvers to request temporary delegation.
   * Allow HR to approve, reject, or cancel delegations.
   * Allow HR to reassign applications when an approver becomes unavailable.

8. **Maintain accurate historical records**

   * Preserve application decisions, comments, changes, reassignment, delegation, and configuration events.
   * Ensure changes to future rules do not alter previously submitted applications.

9. **Generate official leave documentation**

   * Automatically generate an approved leave document after final approval.
   * Provide PDF as the primary format and support additional formats such as DOCX.
   * Allow HR to customize one official leave-document template.

10. **Create a foundation for future LUANAR integration**

    * Use existing LUANAR institutional accounts.
    * Use a temporary HR/admin employee-management interface during development.
    * Keep the employee-data and identity boundaries suitable for later integration with the LUANAR ecosystem.

## Core User Flow

### 1. Employee signs in

1. Employee signs in using their existing LUANAR institutional account.
2. The system identifies the employee and loads their HR-managed profile.
3. The employee can see their:

   * Name
   * Grade
   * Designation
   * Department
   * Date of appointment
   * Annual leave entitlement
   * Current available balance

### 2. Employee creates an application

1. Employee selects **New Leave Application**.
2. Employee selects a leave type.
3. Employee selects a start date.
4. Employee selects an end date.
5. The system calculates the number of working days.
6. The calculation excludes weekends and public holidays.
7. The system validates the dates against the applicable minimum notice period.
8. The system checks that the application does not cross the LUANAR financial-year boundary.
9. The system checks for overlapping leave.
10. The employee provides a reason.
11. The employee uploads supporting documents when required.

### 3. System validates the application

The system checks:

1. The leave type is available to the employee.
2. The requested duration does not exceed the configured maximum.
3. The employee satisfies the leave type's eligibility rules.
4. Required supporting documents are present.
5. The minimum notice period is satisfied.
6. The dates are future working days.
7. The application does not cross a financial-year boundary.
8. The application does not overlap existing leave.
9. The employee has sufficient annual leave balance when annual leave is being requested.

If a critical validation fails, the employee cannot submit the application.

### 4. Employee submits the application

1. Employee reviews the calculated working days and application details.
2. Employee confirms submission.
3. The system generates a unique application reference number.
4. The draft becomes a submitted application.
5. The application is automatically assigned to the first approval stage.
6. The responsible approver receives an email notification.

### 5. Approval workflow begins

The system loads the workflow configured for the employee's category and department/faculty.

Example administration workflow:

`Employee → Supervisor → HOD → Registrar → DVC`

Example academic workflow:

`Employee → HOD → Dean → Registrar → DVC`

Every configured stage is mandatory and must be completed sequentially.

These are examples of what HR configures, not a fixed chain. Approver
positions are HR-managed records (`ApproverRole`) rather than names the
software knows: HR creates the roles a stage may name, decides how much leave
history each role may see, and staffs them either through a **team** (one role
per person per team) or, for a role marked institution-wide, by naming a single
holder. An employee's team decides which chain their applications follow; a
team with no workflow of its own follows the institution-wide one. A stage that
cannot be resolved for a given applicant stops the submission rather than
falling back to someone else.

### 6. Approver reviews the application

The current approver can see:

* Employee information permitted by their role.
* Leave type.
* Leave dates.
* Working days.
* Reason.
* Supporting documents.
* Current leave balance.
* Relevant leave history.
* Previous approval decisions.
* Previous approver comments.

The approver has exactly three actions:

* **Approve**
* **Reject**
* **Return for Correction**

### 7. Application is approved at a stage

1. Approver selects **Approve**.
2. The approver may provide an optional comment.
3. The system records the decision, approver, date, and time.
4. The application moves automatically to the next mandatory stage.
5. The next approver receives an email notification.

### 8. Application is rejected

1. Approver selects **Reject**.
2. A rejection reason is mandatory.
3. The system records the rejection stage, approver, date, time, and reason.
4. The workflow stops.
5. The employee receives an email notification.
6. No annual leave balance is deducted.
7. The employee can edit and resubmit the application.
8. The application keeps its original reference number.
9. A resubmitted application returns to the rejecting approval stage unless HR reassigns it.

### 9. Application is returned for correction

1. Approver selects **Return for Correction**.
2. A correction comment is mandatory.
3. The employee receives an email notification.
4. The employee can edit the application.
5. The employee can replace supporting documents.
6. The employee resubmits the application.
7. The system recalculates working days and revalidates applicable rules.
8. The application returns to the same approver.
9. The approver can see what changed before making a new decision.

### 10. Approver becomes unavailable

1. Approver can submit an unavailability/delegation request.
2. They may nominate a preferred delegate.
3. HR reviews the request.
4. HR must provide a reason when approving or rejecting it.
5. If approved, all pending applications at that approval stage move to the delegate.
6. The delegate receives the same permissions for that stage.
7. When delegation ends, unacted-on applications return to the original approver.
8. Decisions already made by the delegate remain valid.

If an approver becomes unexpectedly unavailable, HR can directly reassign their pending applications.

### 11. Final approval

1. The final configured approver approves the application.
2. The application becomes **Approved**.
3. The system deducts applicable annual leave days.
4. The system calculates the employee's remaining balance.
5. The employee receives an email containing the approved leave details and remaining balance.
6. The supervisor receives the approved leave details.
7. The system generates the official approved leave document.
8. The document becomes available to authorized users.

### 12. Approved leave cancellation

If an employee needs to cancel approved leave before its start date:

1. Employee submits a cancellation request.
2. Employee provides a mandatory cancellation reason.
3. The required Supervisor/HOD approval process handles the cancellation.
4. If approved, the leave is cancelled.
5. Applicable deducted annual leave days are restored to the current financial year's balance.
6. Other relevant workflow members are notified.
7. If cancellation is rejected, the original approved leave remains active and the deducted balance remains unchanged.

## Features

### Employee Management

* LUANAR institutional account authentication.
* HR-managed employee profiles.
* Employee grade assignment.
* Department/faculty assignment.
* Designation/post information.
* Date of appointment.
* Automatically determined annual entitlement.
* Automatically calculated available balance.

### Leave Application

* Create leave applications.
* Save multiple drafts.
* Select leave type.
* Select start and end dates.
* Automatic working-day calculation.
* Weekend exclusion.
* Public-holiday exclusion.
* Minimum notice-period validation.
* Maximum-duration validation.
* Eligibility validation.
* Supporting-document upload.
* Application review before submission.
* Unique reference number generated on submission.
* Overlapping-leave detection.
* Financial-year boundary validation.

### Leave Types and Rules

* Annual leave.
* Maternity leave.
* Paternity leave.
* Compassionate leave.
* HR-configurable additional leave types.
* Configurable maximum duration.
* Configurable eligibility.
* Configurable supporting-document requirement.
* Configurable minimum notice period.
* Future-effective rule changes.

Current default special-leave limits:

* Maternity: 90 days.
* Paternity: 10 days.

These values are configurable by HR.

### Annual Leave Management

* Grade-based annual entitlement.
* Current entitlement configuration:

  * A–C: 21 days.
  * D–G: 24 days.
  * H–U: 30 days.
* Automatic balance calculation.
* Automatic deduction after final approval.
* Automatic restoration after approved cancellation.
* Automatic rejected-leave carry-forward calculation.
* No normal unused-leave carry-forward.
* No individual manual balance editing by HR.
* Future-effective entitlement changes.

### Approval Workflow

* HR-configurable workflows.
* Workflow configuration by employee category and department/faculty.
* Mandatory approval stages.
* Sequential approval.
* Supervisor approval.
* HOD approval.
* Dean approval where configured.
* Registrar approval.
* DVC approval.
* Approve action.
* Reject action.
* Return-for-correction action.
* Optional approval comments.
* Mandatory rejection comments.
* Mandatory correction comments.
* Previous decisions and comments visible to later approvers.

### Workflow Administration

Workflows are not configured on their own. Each team owns one chain, and the
chain is written and edited with the team, so there is never a second screen
where a team's steps can be changed from under it.

* Team-scoped workflow configuration: a chain is created with its team and
  edited on the team's form.
* Future effective dates.
* Workflow validation before activation.
* Active approver validation.
* Required-stage validation.
* Scheduled workflow configuration.
* Temporary delegation.
* Delegate nomination.
* HR delegation approval/rejection.
* Delegation cancellation.
* Automatic return of unacted applications after delegation ends.
* HR emergency reassignment.
* Reassignment audit history.

### Application Tracking

* Application status.
* Approval progress tracker.
* Current approval stage.
* Current responsible approver.
* Approver role.
* Decision dates/times.
* Rejection details.
* Correction details.
* Resubmission.
* Application history.
* Stable reference number throughout the application lifecycle.

### Notifications

V1 uses email notifications for:

* Application submission.
* Approval-stage assignment.
* Approval.
* Rejection.
* Correction request.
* Resubmission.
* Reassignment.
* Delegation events.
* Cancellation requests.
* Cancellation decisions.
* Final approval.

Failed required notifications are logged and reported to HR/administration.

### Supporting Documents

* Upload supporting documents.
* View documents.
* Download documents.
* Required-document validation.
* Document replacement during draft/rejected/correction states.
* Document replacement history.
* Read-only documents during review.
* Read-only documents after approval.

### Approved Leave Documents

* Automatic document generation after final approval.
* PDF generation.
* Support for additional formats such as DOCX.
* One official customizable template.
* HR template customization.
* Automatic population of approved application data.
* Authorized access for employee, supervisor, and HR/personal-file purposes.

### HR Administration

* Employee management.
* Grade management.
* Grade-based entitlement configuration.
* Leave-type configuration.
* Leave-rule configuration.
* Minimum notice configuration.
* Workflow configuration.
* Approver-role configuration: create, rename, and retire the positions a stage may name, and set how much leave history each may see.
* Team configuration: the people who hold a position for a group, the approval steps their applications follow, and an optional campus scope. A team owns its steps; they are never shared with another team.
* Institution-wide role assignment for roles that must have a single holder.
* Future-effective configuration.
* Delegation management.
* Application reassignment.
* Financial-year configuration.
* Leave-document template customization.
* Organization-wide access to finalized applications.

### Audit and History

* Application lifecycle history.
* Approval decisions.
* Rejection reasons.
* Correction comments.
* Resubmissions.
* Cancellation actions.
* Delegation actions.
* Reassignments.
* Rule changes.
* Entitlement configuration changes.
* Workflow configuration changes.
* Document replacement history.
* User and timestamp information for significant actions.

## In Scope

The V1 system will build:

* Web-based leave management.
* Existing LUANAR account authentication boundary.
* Employee profiles.
* HR employee administration for development/testing.
* Grade-based annual leave entitlements.
* Automatic annual leave balance calculations.
* Annual leave applications.
* Maternity leave.
* Paternity leave.
* Compassionate leave.
* Configurable additional leave types.
* Configurable leave rules.
* Future-effective leave-rule changes.
* Working-day calculations.
* Weekend exclusion.
* Public-holiday handling.
* LUANAR financial-year handling.
* Minimum notice periods.
* Leave-duration validation.
* Leave-overlap validation.
* Supporting-document management.
* Multiple application drafts.
* Application submission and reference numbers.
* Sequential approval workflows.
* Role-based access.
* Supervisor/HOD/Dean/Registrar/DVC approval stages where configured.
* Approve/reject/correction actions.
* Approval comments.
* Rejection and correction comments.
* Rejection and resubmission.
* Correction and resubmission.
* Application progress tracking.
* Role-based leave-history access.
* Employee cancellation requests.
* Approved-leave cancellation.
* Automatic balance restoration after approved cancellation.
* Automatic rejected-leave carry-forward calculation.
* Temporary approver delegation.
* HR delegation approval/rejection/cancellation.
* HR emergency reassignment.
* Future-dated workflow changes.
* Workflow validation.
* Email notifications.
* Notification failure logging.
* Automatic approved-document generation.
* Customizable official leave-document template.
* PDF and additional document formats.
* Application and administrative audit history.
* LUANAR financial-year configuration.

## Out of Scope

The V1 system will not build:

* Actual employee attendance tracking.
* Automatic detection of whether an employee actually took approved leave.
* Automatic early-return detection.
* Attendance-system integration.
* In-app notifications.
* Chat or messaging between employees and approvers.
* A replacement for LUANAR's calendar system.
* Workflow simulation or preview/testing mode.
* Employee-controlled approver selection.
* Manual individual employee balance editing by HR.
* Employee-entered accumulated-days calculations.
* Cross-financial-year leave applications.
* Skipping mandatory approval stages.
* Parallel approval workflows.
* Employee-created application accounts separate from LUANAR identity.
* Full LUANAR ecosystem integration before the required institutional integration details are confirmed.
* Automatic employee-data synchronization before the relevant LUANAR integration is available.
* Automatic personal-file integration before the relevant LUANAR HR system is identified.
* Retroactive application of new leave rules to previously submitted applications.
* Retroactive changes to historical approval decisions.
* Broad HR intervention in every normal application.
* Workflow preview/test mode.

## Success Criteria

V1 is considered complete when the following can be demonstrated end-to-end.

### Employee

1. An employee can authenticate using their LUANAR institutional account.
2. The system loads the employee's HR-managed profile.
3. The employee can see their grade, annual entitlement, and calculated balance.
4. The employee can create and save multiple drafts.
5. The employee can select a valid leave type and date range.
6. The system correctly calculates working days.
7. Weekends and public holidays are excluded.
8. The system enforces the configured minimum notice period.
9. The system prevents overlapping leave.
10. The system prevents applications that cross the financial-year boundary.
11. The system prevents annual leave applications exceeding available balance.
12. The system enforces configured special-leave limits and eligibility.
13. The employee can submit a valid application.
14. A unique reference number is generated at submission.
15. The employee can track the application's approval progress.

### Approval

16. A submitted application automatically reaches the configured first approver.
17. Approval stages execute in the configured sequential order.
18. Each approver can approve, reject, or return an application for correction.
19. Approval comments are optional.
20. Rejection and correction comments are mandatory.
21. Later approvers can see permitted previous decisions and comments.
22. Approvers can see the appropriate current balance and leave history based on their role.
23. Rejected applications stop the workflow.
24. Corrected applications return to the same approval stage.
25. Resubmitted applications retain their original reference number.

### Leave Balance

26. Pending applications do not reduce annual leave balance.
27. Rejected applications do not reduce annual leave balance.
28. Final approval deducts applicable annual leave automatically.
29. Approved cancellation restores applicable annual leave automatically.
30. Maternity and paternity leave do not deduct annual leave.
31. Eligible rejected leave is automatically considered for carry-forward.
32. HR cannot manually modify an individual employee's calculated balance.
33. Grade entitlement changes affect future entitlements without rewriting historical applications.

### HR and Workflow Administration

34. HR can configure grade ranges and annual entitlements.
35. HR can assign grades to employees.
36. HR can configure leave-type rules.
37. HR can configure minimum notice periods separately for leave types.
38. HR can configure maximum leave durations.
39. HR can configure eligibility requirements.
40. HR can configure supporting-document requirements.
41. HR can configure approval workflows.
42. Every configured approval stage is mandatory.
43. Workflow stages execute sequentially.
44. Invalid workflow configurations cannot be activated or scheduled.
45. HR can schedule workflow changes for future effective dates.
46. Existing applications retain their original workflow.
47. Approvers can request delegation.
48. HR can approve or reject delegation requests with a reason.
49. All pending applications at a delegated stage move to the delegate.
50. Unacted applications return to the original approver when delegation ends.
51. HR can directly reassign applications when an approver becomes unexpectedly unavailable.

### Notifications and Documents

52. Relevant workflow events generate email notifications.
53. Required notification failures are logged and surfaced to HR/administration.
54. Final approval generates an official leave document automatically.
55. The approved document contains the correct approved application information.
56. HR can customize the single official leave-document template.
57. Authorized users can access approved documents.

### Security, Audit, and Integrity

58. Users can only access information permitted by their role.
59. Leave-history access is restricted to the scope HR configured for the approver role concerned (the same department, the same faculty, the current financial year, or nothing) rather than to any role name the software recognises.
60. Approvers cannot modify employee leave balances.
61. Employees cannot modify HR-managed grade or entitlement information.
62. Significant workflow, application, configuration, and administrative actions are recorded in the audit history.
63. Historical application decisions remain unchanged when future rules are modified.
64. The complete lifecycle of an application can be traced from submission through final decision.

### End-to-End Definition of Done

The V1 system is considered operationally complete when a test employee can:

`Log in → Create application → Validate dates/rules → Submit → Automatically route through configured approvers → Approve/Reject/Correct → Calculate balance → Generate approved document → Notify relevant users → Preserve complete history`

without requiring HR to manually calculate balances or manually forward normal applications.


