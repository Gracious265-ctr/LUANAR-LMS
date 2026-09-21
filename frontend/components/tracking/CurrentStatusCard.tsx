import { formatDateTime } from "@/lib/tracking/format";
import { STATUS_META } from "@/lib/tracking/labels";
import type { TrackingResponse } from "@/lib/tracking/types";
import type { ReactNode } from "react";

/**
 * Full-width card composed purely from response fields (backend authority: the
 * frontend joins copy to enum values, it never computes status or stage).
 */
export function CurrentStatusCard({ data }: { data: TrackingResponse }) {
  const meta = STATUS_META[data.status];
  const Icon = meta.icon;
  const { current_stage, rejection, correction } = data;

  const headline = statusHeadline(data);
  const sublines = statusSublines(data);

  return (
    <section
      aria-label="Current status"
      className="rounded-xl border border-border-default bg-surface-card shadow-subtle"
    >
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <div
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${meta.badgeClass}`}
        >
          <Icon className="h-6 w-6" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="break-words text-lg font-semibold text-text-primary">
            {headline}
          </h2>
          {sublines.length > 0 && (
            <div className="mt-1 space-y-0.5 text-sm text-text-secondary">
              {sublines.map((line, index) => (
                <p key={index} className="break-words">
                  {line}
                </p>
              ))}
            </div>
          )}
          {data.status === "pending" && current_stage && (
            <p className="mt-2 text-xs text-text-muted">
              Assigned {formatDateTime(current_stage.assigned_at)}
            </p>
          )}
        </div>
        {rejection && (
          <p className="sm:ml-auto max-w-md break-words rounded-lg bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected">
            {rejection.reason}
          </p>
        )}
        {correction && (
          <p className="sm:ml-auto max-w-md break-words rounded-lg bg-status-correction-subtle px-3 py-2 text-sm text-status-correction">
            {correction.comment}
          </p>
        )}
      </div>
    </section>
  );
}

function statusHeadline(data: TrackingResponse): ReactNode {
  const { status, current_stage, rejection, correction, approved_at } = data;
  switch (status) {
    case "pending":
      return (
        <>
          Awaiting <strong>{current_stage?.role_label}</strong> review
        </>
      );
    case "approved":
      return <>Fully approved on {formatDateTime(approved_at)}</>;
    case "rejected":
      return (
        <>
          Rejected at the{" "}
          <strong>{rejection?.role_label}</strong> stage on{" "}
          {formatDateTime(rejection?.decided_at)}
        </>
      );
    case "correction_required":
      return (
        <>
          Returned for correction by{" "}
          <strong>{correction?.role_label}</strong> — action needed from you
        </>
      );
    case "cancelled":
      return <>This application has been cancelled</>;
    default:
      return "Application status";
  }
}

function statusSublines(data: TrackingResponse): string[] {
  const lines: string[] = [];
  const { status, current_stage } = data;
  if (status === "pending" && current_stage) {
    const parts = [`with ${current_stage.approver_name}`];
    if (current_stage.is_delegate && current_stage.on_behalf_of) {
      parts.push(`(acting for ${current_stage.on_behalf_of})`);
    }
    lines.push(parts.join(" "));
    lines.push(`Step ${current_stage.order} of ${data.stages.length}`);
  }
  return lines;
}