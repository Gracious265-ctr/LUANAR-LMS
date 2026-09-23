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
  );
}