import type { ResubmissionValidationIssue } from "@/lib/applications/resubmission-types";

/**
 * Validation-error panel for save/resubmit 400s. Each issue is labelled by its
 * field so screen readers can associate the message with the form control.
 */
export function ValidationErrorsPanel({
  issues,
}: {
  issues: ResubmissionValidationIssue[];
}) {
  if (issues.length === 0) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-lg border border-border-error bg-status-rejected-subtle p-4"
    >
      <h3 className="text-sm font-semibold text-status-rejected">
        Fix the following before continuing
      </h3>
      <ul className="mt-2 space-y-1.5">
        {issues.map((issue, index) => (
          <li
            key={`${issue.code}-${index}`}
            className="text-sm text-status-rejected"
          >
            <span className="font-medium">{fieldLabel(issue.field)}: </span>
            {issue.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    leave_type_id: "Leave type",
    start_date: "Start date",
    end_date: "End date",
    reason: "Reason",
    documents: "Documents",
    working_days: "Working days",
    row_version: "Storage",
  };
  return labels[field] ?? field;
}