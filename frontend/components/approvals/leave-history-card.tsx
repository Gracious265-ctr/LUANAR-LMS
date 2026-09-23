import { History } from "lucide-react";

import { formatDateRange, leaveHistoryNote } from "@/lib/approvals/format";
import type { ApprovalDetail, LeaveHistoryItem } from "@/lib/approvals/types";

import { StatusBadge } from "../tracking/StatusBadge";
import { Card } from "./primitives";

export function LeaveHistoryCard({ detail }: { detail: ApprovalDetail }) {
  const history = detail.leave_history;

  if (!history.available) {
    return (
      <Card title="Leave history" icon={<History className="h-4 w-4" />}>
        <p className="text-sm text-text-muted">
          {leaveHistoryNote(history)}
        </p>
      </Card>
    );
  }

  return (
    <Card title="Leave history" icon={<History className="h-4 w-4" />}>
      <p className="mb-3 text-xs text-text-muted">{leaveHistoryNote(history)}</p>
      {history.items.length === 0 ? (
        <p className="text-sm text-text-muted">No leave history to display.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[440px] text-left text-sm">
            <thead>
              <tr className="border-b border-border-default text-xs tracking-wide text-text-secondary uppercase">
                <th scope="col" className="py-2 pr-4 font-medium">
                  Leave type
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  Dates
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  Days
                </th>
                <th scope="col" className="py-2 font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {history.items.map((item, i) => (
                <LeaveHistoryRow key={`${item.leave_type}-${i}`} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function LeaveHistoryRow({ item }: { item: LeaveHistoryItem }) {
  return (
    <tr>
      <td className="py-2.5 pr-4 font-medium text-text-primary">
        {item.leave_type}
      </td>
      <td className="py-2.5 pr-4 text-text-secondary">
        {formatDateRange(item.start_date, item.end_date)}
      </td>
      <td className="py-2.5 pr-4 text-text-secondary">{item.working_days}</td>
      <td className="py-2.5">
        <StatusBadge status={item.status} />
      </td>
    </tr>
  );
}