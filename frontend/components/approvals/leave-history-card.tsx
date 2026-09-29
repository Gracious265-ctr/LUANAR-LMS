import { Clock } from "lucide-react";

import { formatDate } from "@/lib/approvals/format";
import { STATUS_META } from "@/lib/approvals/labels";
import type { StatusMeta } from "@/lib/approvals/labels";
import type { ApprovalReview } from "@/lib/approvals/types";

import { Panel } from "./panel";
import { StatusBadge } from "./badges";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="py-2 pr-3">Reference</TableHead>
              <TableHead className="py-2 pr-3">Leave type</TableHead>
              <TableHead className="py-2 pr-3">Dates</TableHead>
              <TableHead className="py-2 pr-3">Days</TableHead>
              <TableHead className="py-2">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.entries.map((entry) => {
              const meta = STATUS_META[entry.status] ?? FALLBACK_META;
              const Icon = meta.icon;
              return (
                <TableRow key={entry.id}>
                  <TableCell className="py-2.5 pr-3 font-medium text-text-primary">
                    {entry.reference}
                  </TableCell>
                  <TableCell className="py-2.5 pr-3 text-text-secondary">
                    {entry.leave_type.name}
                  </TableCell>
                  <TableCell className="py-2.5 pr-3 text-text-secondary">
                    {formatDate(entry.start_date) || "—"} → {formatDate(entry.end_date) || "—"}
                  </TableCell>
                  <TableCell className="py-2.5 pr-3 text-text-secondary">
                    {entry.working_days}
                  </TableCell>
                  <TableCell className="py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
                      <Icon className={meta.dotClass} aria-hidden="true" />
                      {meta.label}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Panel>
  );
}

export { StatusBadge };