## Application Building Context

Read the following files in order before implementing
or making any architectural decision:

1. `context/project-overview.md` — product definition,
   goals, features, and scope
2. `context/architecture.md` — system structure,
   boundaries, storage model, and invariants
3. `context/ui-context.md` — theme, colors, typography,
   and component conventions
4. `context/code-standards.md` — implementation rules
   and conventions
5. `context/ai-workflow-rules.md` — development workflow,
   scoping rules, and delivery approach
6. `context/progress-tracker.md` — current phase,
   completed work, open questions, and next steps
7. `context/troubleshooting-notes.md` — known errors,
   root causes, and fixes accumulated from past work

Update `context/progress-tracker.md` after each
meaningful implementation change.

If implementation changes the architecture, scope, or
standards documented in the context files, update the
relevant file before continuing.

Whenever you hit an error, bug, or debugging session —
in any session, on any branch — record it in
`context/troubleshooting-notes.md` before moving on, in the
same shape as the existing entries (symptom / root cause /
what to look for / fix). Check that file first when a failure
resembles one already documented.
