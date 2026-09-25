import { Clock } from "lucide-react";

import { formatDate } from "@/lib/approvals/format";
import { STATUS_META } from "@/lib/approvals/labels";
import type { StatusMeta } from "@/lib/approvals/labels";
import type { ApprovalReview } from "@/lib/approvals/types";

import { Panel } from "./panel";
import { StatusBadge } from "./badges";

const FALLBACK_META: StatusMeta = {
  label: "Submitted",
  icon: Clock,
  badgeClass: "bg-surface-secondary text-text-secondary",
  textClass: "text-text-secondary",
  dotClass: "bg-text-muted",
};

export function LeaveHistoryCard({ data }: { data: ApprovalReview }) {
  const history = data.history.leave_history;

  if (!history.available) {
    return (
      <Panel title="Leave history">
        <p className="text-sm text-text-secondary">
          Leave history is not available for your role.
        </p>
      </Panel>
    );
  }

  const scopeNote =
    history.scope === "current_financial_year"
      ? "Showing leave within the current financial year."
      : "Showing the employee's full leave history.";

  return (
    <Panel title="Leave history">
      <p className="mb-4 text-xs text-text-muted">{scopeNote}</p>
      {history.entries.length === 0 ? (
        <p className="text-sm text-text-secondary">
          No other leave applications are visible in this scope.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
                <th className="py-2 pr-3 font-medium">Reference</th>
                <th className="py-2 pr-3 font-medium">Leave type</th>
                <th className="py-2 pr-3 font-medium">Dates</th>
                <th className="py-2 pr-3 font-medium">Days</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {history.entries.map((entry) => {
                const meta = STATUS_META[entry.status] ?? FALLBACK_META;
                const Icon = meta.icon;
                return (
                  <tr key={entry.id} className="border-b border-border-default last:border-b-0">
                    <td className="py-2.5 pr-3 font-medium text-text-primary">
                      {entry.reference}
                    </td>
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {entry.leave_type.name}
                    </td>
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {formatDate(entry.start_date) || "—"} → {formatDate(entry.end_date) || "—"}
                    </td>
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {entry.working_days}
                    </td>
                    <td className="py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
                        <Icon className={meta.dotClass} aria-hidden="true" />
                        {meta.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export { StatusBadge };