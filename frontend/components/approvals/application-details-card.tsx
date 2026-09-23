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
  );
}