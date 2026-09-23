"use client";

import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import type { ResubmissionContent } from "@/lib/applications/resubmission-types";

import { DateRangeFields } from "../../leave/DateRangeFields";
import { LeaveTypeSelect } from "../../leave/LeaveTypeSelect";
import { WorkingDaysPreview } from "../../leave/WorkingDaysPreview";

/**
 * Controlled edit form for a rejected / correction-required application. Live
 * working-days validation reuses the shared endpoint with ``application_id`` so
 * the application's own overlap is excluded.
 */
export function ResubmissionForm({
  applicationId,
  content,
  onChange,
  readOnly,
}: {
  applicationId: string;
  content: ResubmissionContent;
  onChange: (patch: Partial<ResubmissionContent>) => void;
  readOnly?: boolean;
}) {
  const validation = useLeaveValidation(
    {
      leave_type_id: content.leave_type_id,
      start_date: content.start_date,
      end_date: content.end_date,
      application_id: applicationId,
    },
    { enabled: Boolean(content.start_date && content.end_date) }
  );

  const errorFor = (field: string): string | null =>
    (validation.result?.errors ?? []).find((issue) => issue.field === field)
      ?.message ?? null;

  const startError = errorFor("start_date");
  const endError = errorFor("end_date");
  const leaveTypeError = errorFor("leave_type");
  const reasonError = errorFor("reason");
  const topIssues = (validation.result?.errors ?? []).filter((issue) =>
    ["documents", "—"].includes(issue.field)
  );

  return (
    <div className="space-y-4">
      {leaveTypeError && <FieldError message={leaveTypeError} />}
      <LeaveTypeSelect
        value={content.leave_type_id}
        disabled={readOnly}
        onChange={(value) => onChange({ leave_type_id: value })}
      />

      <DateRangeFields
        startDate={content.start_date ?? ""}
        endDate={content.end_date ?? ""}
        onStartChange={(value) => onChange({ start_date: value || null })}
        onEndChange={(value) => onChange({ end_date: value || null })}
      />
      {startError && <FieldError message={startError} />}
      {endError && <FieldError message={endError} />}

      <WorkingDaysPreview
        days={
          content.start_date && content.end_date
            ? (validation.result?.working_days ?? null)
            : null
        }
        loading={Boolean(content.start_date && content.end_date) && validation.isLoading}
      />

      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-secondary">
          Reason
        </label>
        <textarea
          value={content.reason}
          onChange={(event) => onChange({ reason: event.target.value })}
          rows={3}
          disabled={readOnly}
          placeholder="Provide a reason for your leave application..."
          className="w-full resize-none rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus disabled:bg-surface-muted"
        />
        {reasonError && <FieldError message={reasonError} />}
      </div>

      {topIssues.length > 0 && (
        <div
          role="alert"
          className="rounded-lg border border-border-error bg-status-rejected-subtle p-3"
        >
          {topIssues.map((issue) => (
            <p key={issue.code} className="text-sm text-status-rejected">
              {issue.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function FieldError({ message }: { message: string }) {
  return (
    <p role="alert" className="text-sm text-status-rejected">
      {message}
    </p>
  );
}