<<<<<<< HEAD
import { CalendarRange, Info } from "lucide-react";

import { formatDateRange } from "@/lib/approvals/format";
import type { ApprovalDetail } from "@/lib/approvals/types";

import { Card, DataRow } from "./primitives";

export function ApplicationDetailsCard({ detail }: { detail: ApprovalDetail }) {
  const { application } = detail;
  return (
    <Card
      title="Application details"
      icon={<CalendarRange className="h-4 w-4" />}
    >
      <dl className="divide-y divide-border-default">
        <DataRow label="Leave type" value={application.leave_type} />
        <DataRow
          label="Dates"
          value={formatDateRange(application.start_date, application.end_date)}
        />
        <DataRow
          label="Working days"
          value={
            <span className="inline-flex items-center gap-1.5">
              {application.working_days}
              <span
                className="text-text-muted"
                title="Working days exclude weekends and public holidays"
              >
                <Info className="h-3.5 w-3.5" aria-hidden="true" />
              </span>
            </span>
          }
        />
      </dl>
      <div className="mt-3">
        <p className="mb-1.5 text-sm text-text-secondary">Reason</p>
        <p className="rounded-lg bg-surface-subtle px-4 py-3 text-sm break-words whitespace-pre-line text-text-primary">
          {application.reason || "No reason provided."}
        </p>
      </div>
    </Card>
=======
import { formatDate, formatDateTime } from "@/lib/approvals/format";
import type { ApprovalReview } from "@/lib/approvals/types";

import { DetailRow, Panel } from "./panel";

export function ApplicationDetailsCard({ data }: { data: ApprovalReview }) {
  const app = data.application;
  const leaveType = data.rules.leave_type.name || "Leave";
  return (
    <Panel title="Application details">
      <dl className="divide-y divide-border-default">
        <DetailRow label="Leave type">
          <span className="font-medium">{leaveType}</span>
        </DetailRow>
        <DetailRow label="Start date">{formatDate(app.start_date) || "—"}</DetailRow>
        <DetailRow label="End date">{formatDate(app.end_date) || "—"}</DetailRow>
        <DetailRow label="Working days">{app.working_days}</DetailRow>
        <DetailRow label="Calendar days">{app.calendar_days}</DetailRow>
        <DetailRow label="Submitted">
          {formatDateTime(app.submitted_at) || "—"}
        </DetailRow>
        <DetailRow label="Financial year">
          {app.financial_year_label || "—"}
        </DetailRow>
        <DetailRow label="Reason">
          <span className="whitespace-pre-wrap">{app.reason || "—"}</span>
        </DetailRow>
      </dl>
    </Panel>
>>>>>>> feature/plans-teams
  );
}