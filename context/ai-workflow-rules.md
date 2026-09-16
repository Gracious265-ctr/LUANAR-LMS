

# AI Workflow Rules

These rules are mandatory for every AI coding agent working on the LUANAR Leave Management System.

The agent must follow these rules regardless of the AI tool, model, IDE, or developer using it.

---

## 1. Overall Approach

- Work from approved specifications.
- Treat the project's Markdown documentation as the source of truth for permanent architecture, business rules, workflows, and implementation decisions.
- Implement the system incrementally.
- Complete one implementation unit before starting another.
- Understand the existing code before modifying it.
- Inspect the relevant architecture, requirements, code, and tests before implementing a unit.
- Reuse existing project patterns before introducing new patterns.
- Make the smallest change that completely satisfies the current specification.
- Preserve existing behavior unless the specification explicitly requires a behavior change.
- Do not implement features based on assumptions about future requirements.
- Do not optimize or refactor unrelated code while implementing a unit.
- Treat AI-generated code as production code that must satisfy all project code standards and verification requirements.

---

## 2. Specification-Driven Development

- Do not begin implementation until the current unit has a clear specification.
- Read the complete specification before changing code.
- Identify the unit's goal, affected system boundary, dependencies, implementation requirements, verification requirements, and documentation updates before coding.
- Treat the approved specification as the implementation boundary.
- Implement only what is required by the current unit.
- Do not expand a unit because you identify potentially useful improvements while implementing it.
- Record important permanent decisions in the appropriate documentation instead of leaving them only in the conversation.
- If implementation reveals that the specification is incorrect or incomplete, stop at the affected decision point and resolve the requirement before proceeding.

---

## 3. One Unit at a Time

- Work on exactly one implementation unit at a time.
- Do not begin the next unit until the current unit satisfies its completion criteria.
- Do not combine multiple unrelated features into one implementation unit.
- Do not implement future units merely because their supporting code is being touched.
- Keep changes directly related to the current unit.
- If a required dependency belongs to another unit, implement only the minimum dependency required to unblock the current unit.
- Do not use a future feature as justification for speculative architecture.

The active unit must have:

1. A defined goal.
2. A defined visible result.
3. A defined system boundary.
4. Defined dependencies.
5. Defined verification criteria.
6. Defined documentation updates where applicable.

---

## 4. Incremental Implementation

- Implement the smallest complete slice of functionality that satisfies the current requirement.
- Prefer vertical slices when a feature crosses frontend, backend, and database boundaries.
- Complete the required data model, backend behavior, API boundary, UI behavior, and verification for the current slice before expanding its scope.
- Keep intermediate changes understandable and reviewable.
- Do not create large batches of unrelated changes.
- Run verification after meaningful implementation milestones.
- Fix failures before adding additional complexity.

---

## 5. Scoping Rules

- Stay inside the scope of the active unit.
- Do not modify unrelated features.
- Do not redesign the application while implementing a functional requirement.
- Do not refactor unrelated code because it appears cleaner.
- Do not introduce new dependencies unless the current unit requires them.
- Do not change the database schema unless the current unit requires the change.
- Do not change API contracts unless the current unit requires the change.
- Do not change authentication or authorization behavior unless the current unit explicitly covers it.
- Do not change established business rules without an approved requirement.
- Do not replace an existing implementation merely because another approach is personally preferred.
- Do not add future-proof abstractions without a current requirement that justifies them.

---

## 6. No Speculative Changes

- Do not implement features that have only been discussed as possible future functionality.
- Do not create unused database fields for anticipated features.
- Do not create unused API endpoints.
- Do not create unused services.
- Do not create unused components.
- Do not add configuration options that the current requirements do not use.
- Do not add integrations before their requirements and technical constraints are confirmed.
- Do not select infrastructure technologies that are explicitly marked as TBD.
- Do not invent organization-specific behavior to fill documentation gaps.
- Do not assume how LUANAR infrastructure works when the architecture document marks it as TBD.

---

## 7. When to Split Work

Split the current unit into smaller implementation steps when any of the following occurs:

- The unit crosses multiple independent system boundaries.
- The unit requires a database change followed by substantial backend logic and frontend work.
- The unit contains multiple independently verifiable behaviors.
- The implementation becomes difficult to review as one change.
- A step cannot be safely verified without completing another independent step first.
- The current implementation would require modifying many unrelated files.
- A single step would create a large amount of unverified code.
- A failure cannot be isolated because too many changes are being made simultaneously.

When splitting a unit:

- Preserve the original unit goal.
- Define each smaller step explicitly.
- Give each step one primary responsibility.
- Verify each step before proceeding where practical.
- Do not turn the split into an opportunity to add unrelated functionality.
- Keep the smaller steps within the original unit's scope.

---

## 8. Handling Missing Requirements

- Do not invent missing business requirements.
- First inspect existing project documentation and implementation for the required information.
- Search for an existing decision before declaring a requirement missing.
- If the requirement genuinely does not exist, identify exactly what decision is missing.
- Continue with implementation only when the missing information does not affect correctness or can safely remain an explicitly documented TBD.
- If the missing information affects business behavior, security, data integrity, authorization, workflow, or architecture, stop the affected implementation and request clarification.
- Do not silently choose a behavior merely because it is technically convenient.
- Record confirmed decisions in the appropriate project documentation.

---

## 9. Handling Ambiguous Requirements

- Identify the specific ambiguity before asking for clarification.
- Do not ask broad questions when the ambiguity can be isolated to one decision.
- Prefer concrete alternatives when asking for clarification.
- Do not make an irreversible architectural or business-rule decision based on an ambiguous requirement.
- If a safe interpretation is explicitly supported by existing documentation, follow that documented interpretation.
- If multiple interpretations remain possible and they would produce different behavior, stop and request clarification.
- Once the decision is confirmed, update the relevant specification or source-of-truth document before completing the affected unit.

---

## 10. Existing Code Investigation

Before modifying an existing area:

- Locate the relevant files.
- Read the surrounding implementation.
- Identify existing services, utilities, components, models, serializers, permissions, and tests that already solve part of the problem.
- Identify dependencies between the code being changed and existing functionality.
- Follow established project patterns unless the specification explicitly requires changing them.
- Do not assume a missing feature means the supporting infrastructure is missing.
- Do not create a duplicate implementation before checking for an existing one.
- Identify whether the requested change affects existing API contracts or database behavior before modifying them.

---

## 11. Protected Files and Areas

Do not modify the following without explicit instruction from the developer or an approved specification requiring the change:

### Generated UI Components

- Do not directly modify generated `shadcn/ui` component implementations merely to customize their appearance.
- Prefer composition, props, variants, wrappers, and application-level styling.
- Modify a generated component only when the current specification explicitly requires changing its underlying implementation.
- Preserve accessibility and behavior when modifying a generated component.

### Generated Files

- Do not manually modify generated files when the source configuration or generator is the authoritative source.
- Modify the source and regenerate the output when regeneration is the established project process.

### Environment and Secrets

- Do not modify production environment configuration without explicit instruction.
- Do not commit `.env` files containing secrets.
- Do not replace credentials or authentication configuration based on assumptions.

### Database Migrations

- Do not edit an already-applied migration to change historical database behavior.
- Create a new migration when an existing schema requires a subsequent change.
- Do not delete migrations to make a schema problem disappear.

### Configuration

- Do not change project-wide configuration merely to make the current unit easier to implement.
- If configuration must change, identify why the current unit requires it and verify that existing functionality remains valid.

### Shared Infrastructure

- Do not replace authentication, API clients, storage abstractions, workflow engines, or other shared infrastructure without an explicit requirement.
- Do not change shared infrastructure for the convenience of one feature when a local solution satisfies the specification.

---

## 12. Frontend Rules

- Keep frontend responsibilities within the boundaries defined in `architecture.md`.
- Do not move authoritative business rules into the frontend.
- Do not calculate authoritative leave balances in the frontend.
- Do not determine approval permissions in the frontend.
- Do not determine workflow progression in the frontend.
- Do not trust frontend validation as a replacement for backend validation.
- Reuse existing components before creating new ones.
- Follow the project's established component organization.
- Keep reusable UI in `components/`.
- Do not place business logic inside presentational components.
- Do not introduce `"use client"` unless client-side behavior requires it.
- Preserve existing responsive and theme behavior when implementing functional changes.
- Do not perform unrelated visual redesign during functional implementation.

---

## 13. Backend Rules

- Keep authoritative business logic in Django.
- Validate all client input on the backend.
- Enforce authorization on every protected operation.
- Validate resource ownership and organizational scope server-side.
- Keep API handlers thin.
- Place complex business operations in appropriate backend services/domain modules.
- Use database transactions when a business operation requires multiple related records to remain consistent.
- Do not bypass existing domain services to modify records directly.
- Do not trust identifiers, roles, balances, or calculated values supplied by the frontend.
- Preserve existing API contracts unless the active specification requires a change.

---

## 14. Business-Rule Protection

Treat the following as protected business rules unless an approved requirement explicitly changes them:

- Employees cannot manipulate their own authoritative leave balance.
- Pending leave does not deduct annual leave.
- Rejected leave does not deduct annual leave.
- Correction-required leave does not deduct annual leave.
- Annual leave is deducted only after final approval.
- Approved cancellation restores applicable annual leave.
- Special leave does not deduct annual leave unless its configured rule explicitly says otherwise.
- Working-day calculations exclude weekends and configured public holidays.
- Leave cannot start on the application/submission date.
- Leave cannot start in the past.
- Leave cannot cross a financial-year boundary.
- Approval stages execute sequentially.
- Mandatory workflow stages cannot be skipped.
- Rejection stops the workflow.
- Correction returns the application to the responsible stage.
- Resubmission retains the original reference number.
- Submitted applications retain their applicable historical workflow and rule context.

Do not alter these behaviors while implementing an unrelated unit.

---

## 15. Documentation Synchronization

- Treat project documentation as part of the implementation, not optional supplementary material.
- Update documentation whenever implementation changes a permanent architecture, business rule, workflow, API contract, data model, storage decision, or development process.
- Update the affected source-of-truth document before marking the implementation unit complete.
- Do not leave permanent decisions only in source code or chat history.
- Do not update documentation to describe behavior that has not actually been implemented.
- Keep documentation consistent with the current codebase.
- Remove outdated documentation when a confirmed decision replaces it.
- Preserve historical context when required for understanding existing records or migrations.
- If implementation exposes a documentation conflict, resolve the conflict before completing the unit.

At minimum, evaluate whether the following documents require updates:

```text
project-overview.md
requirements.md
business-rules.md
architecture.md
code-standards.md
ai-workflow-rules.md
````

Update only the documents affected by the current change.

---

## 16. Database Changes

Before changing the database:

* Confirm that the current unit requires the change.
* Inspect the existing models and relationships.
* Check whether the required data structure already exists.
* Design the smallest schema change that satisfies the requirement.
* Create the appropriate Django migration.
* Consider existing records and migration safety.
* Verify constraints and relationships.
* Test the migration.
* Update relevant documentation if the data model represents a permanent architectural decision.

Do not introduce database structures solely for future functionality.

---

## 17. API Changes

Before creating or modifying an endpoint:

* Check whether an existing endpoint already provides the required operation.
* Confirm the endpoint belongs to the active unit.
* Define its input and output behavior.
* Validate authentication requirements.
* Validate authorization requirements.
* Validate ownership and organizational scope.
* Implement backend validation.
* Preserve consistent response and error structures.
* Update API documentation if the endpoint becomes part of the project's permanent API contract.
* Add tests for successful, invalid, unauthorized, and forbidden requests where applicable.

Do not create multiple endpoints that perform the same business operation without a documented reason.

---

## 18. Testing and Verification

Before moving to the next implementation unit, verify all applicable items below:

### Scope

* [ ] Only the active unit was implemented.
* [ ] No speculative functionality was introduced.
* [ ] No unrelated behavior was changed.
* [ ] No unnecessary dependencies were added.

### Code Quality

* [ ] Code follows `code-standards.md`.
* [ ] Existing project patterns were reused where applicable.
* [ ] No dead code remains.
* [ ] No debugging statements remain.
* [ ] No secrets were introduced.
* [ ] Protected/generated files were not modified without authorization.

### Backend

* [ ] Backend validation is implemented.
* [ ] Authorization is enforced.
* [ ] Ownership and organizational scope are enforced.
* [ ] Business rules are enforced server-side.
* [ ] Database operations are consistent and transactional where required.

### Frontend

* [ ] UI behavior matches the specification.
* [ ] Loading, success, empty, and error states are handled where applicable.
* [ ] Frontend does not contain authoritative business logic.
* [ ] Existing component and styling conventions are preserved.

### Business Behavior

* [ ] Relevant business-rule tests pass.
* [ ] Invalid cases are tested.
* [ ] Permission boundaries are tested.
* [ ] State transitions are tested where applicable.
* [ ] Existing functionality affected by the change remains functional.

### Documentation

* [ ] `architecture.md` was checked for affected architectural decisions.
* [ ] `requirements.md` was checked for affected requirements.
* [ ] `business-rules.md` was checked for affected rules.
* [ ] Other relevant source-of-truth documentation was updated.
* [ ] Documentation accurately reflects the implemented behavior.

### Verification

* [ ] Relevant automated tests pass.
* [ ] Relevant linting/type checks pass.
* [ ] The application builds successfully where applicable.
* [ ] Relevant manual verification has been performed.
* [ ] No known blocking errors remain.

Do not start the next unit until all applicable verification requirements are satisfied.

---

## 19. Handling Verification Failures

* Do not ignore failing tests.
* Do not disable tests to make the unit pass.
* Do not weaken validation solely to satisfy an existing test unless the test itself is demonstrably incorrect and the change is approved.
* Identify the root cause of the failure.
* Fix the root cause within the current unit's scope.
* If the failure belongs to another feature or reveals an unrelated pre-existing problem, document it and do not expand the current unit unnecessarily.
* Do not mark the unit complete while a failure directly caused by the implementation remains unresolved.

---

## 20. Agent Communication

When reporting completed work:

* State exactly what was implemented.
* Identify the files that were changed.
* Identify any database migrations created.
* Identify tests and verification performed.
* Identify documentation that was updated.
* Identify unresolved issues or explicitly documented TBDs.
* Do not claim functionality was tested when it was not tested.
* Do not claim a requirement was implemented when the code only partially satisfies it.
* Do not hide implementation limitations.
* Do not describe speculative future work as completed functionality.

When blocked:

* State the exact blocking requirement or technical issue.
* Explain why the missing decision affects implementation.
* Identify the smallest decision needed to continue.
* Do not invent a requirement to unblock yourself.

---

## 21. Completion Rule

An implementation unit is complete only when:

1. The approved specification has been implemented.
2. The implementation remains within the unit's scope.
3. Existing functionality has not been unintentionally broken.
4. Required validation and authorization are enforced.
5. Relevant tests pass.
6. Required verification has been performed.
7. Required documentation has been updated.
8. No speculative changes remain.
9. No unresolved implementation error remains within the unit.
10. The code is ready for review by the other project developer.

After completing these requirements, stop the current unit.

Do not automatically begin the next unit.

```
```

