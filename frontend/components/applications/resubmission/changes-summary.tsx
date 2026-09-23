import { ArrowRight, CornerDownRight } from "lucide-react";

import { formatDate } from "@/lib/tracking/format";
import type { ChangesPreview } from "@/lib/applications/resubmission-types";

/**
 * Change summary (spec sections 4 & 9): field rows plus added/removed/replaced
 * document lists. Shared by the resubmission preview and the approver's
 * "Changes since decision" card.
 */
export function ChangesSummary({
  changes,
  compact = false,
}: {
  changes: ChangesPreview | null;
  compact?: boolean;
}) {
  if (!changes || !changes.has_changes) {
    return (
      <p className="text-sm text-text-muted">
        No changes were made to the application content.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {changes.fields.length > 0 && (
        <dl className="divide-y divide-border-default rounded-lg border border-border-default">
          {changes.fields.map((field) => (
            <div
              key={field.field}
              className="grid grid-cols-1 gap-1 px-3 py-2 sm:grid-cols-[1fr_auto] sm:items-center sm:gap-4"
            >
              <dt className="min-w-0 text-sm font-medium text-text-primary">
                {field.label}
              </dt>
              <dd className={compact ? undefined : "min-w-0 sm:text-right"}>
                <span className="inline-flex max-w-full min-w-0 items-center gap-2 text-sm">
                  <span
                    className="truncate text-text-muted line-through"
                    title={renderValue(field.field, field.before)}
                  >
                    {renderValue(field.field, field.before)}
                  </span>
                  <ArrowRight
                    className="h-3.5 w-3.5 shrink-0 text-brand-primary"
                    aria-hidden="true"
                  />
                  <span
                    className="truncate font-medium text-text-primary"
                    title={renderValue(field.field, field.after)}
                  >
                    {renderValue(field.field, field.after)}
                  </span>
                </span>
              </dd>
            </div>
          ))}
        </dl>
      )}

      {(changes.documents.added.length > 0 ||
        changes.documents.removed.length > 0 ||
        changes.documents.replaced.length > 0) && (
        <ul className="space-y-1.5 text-sm">
          {changes.documents.added.map((doc) => (
            <li
              key={`added-${doc.name}`}
              className="flex items-center gap-2 text-text-primary"
            >
              <span className="text-status-approved">+</span>
              <span className="truncate">{doc.name}</span>
            </li>
          ))}
          {changes.documents.removed.map((doc) => (
            <li
              key={`removed-${doc.name}`}
              className="flex items-center gap-2 text-text-primary"
            >
              <span className="text-status-rejected">−</span>
              <span className="truncate">{doc.name}</span>
            </li>
          ))}
          {changes.documents.replaced.map((doc) => (
            <li
              key={`replaced-${doc.old_name}`}
              className="flex items-center gap-2 text-text-primary"
            >
              <CornerDownRight
                className="h-3.5 w-3.5 shrink-0 text-brand-primary"
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="text-text-muted line-through">
                  {doc.old_name}
                </span>
                <ArrowRight
                  className="mx-1 inline h-3.5 w-3.5 text-text-muted"
                  aria-hidden="true"
                />
                <span className="truncate">{doc.new_name}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function renderValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (
    (field === "start_date" || field === "end_date") &&
    typeof value === "string"
  ) {
    return formatDate(value);
  }
  if (typeof value === "string" || typeof value === "number")
    return String(value);
  return JSON.stringify(value);
}