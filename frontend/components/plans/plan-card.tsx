import { AlertTriangle, ChevronRight } from "lucide-react";
import Link from "next/link";

import { formatDate } from "@/lib/plans/format";
import type { PlanRow } from "@/lib/plans/types";
import { cn } from "@/lib/utils";

import { BlockStatusBadge, PlanStatusBadge } from "./plan-status-badge";

export function PlanCard({
  plan,
  showEmployee = false,
  footer,
}: {
  plan: PlanRow;
  showEmployee?: boolean;
  footer?: React.ReactNode;
}) {
  const conflictCount = plan.peer_conflicts?.length ?? 0;
  return (
    <Link
      href={`/dashboard/plans/${plan.id}`}
      className="block rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle transition-colors hover:bg-surface-hover"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            {showEmployee && (
              <h3 className="text-sm font-semibold text-text-primary">
                {plan.employee_name}
              </h3>
            )}
            <span className="text-sm text-text-secondary">
              {formatDate(plan.period_start)} → {formatDate(plan.period_end)}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-text-muted">
            {plan.financial_year_label || "—"} · {plan.working_days}{" "}
            {plan.working_days === 1 ? "day" : "days"} planned
          </p>
        </div>
        <div className="flex items-center gap-2">
          {conflictCount > 0 && (
            <span
              title="Peer conflict warning"
              className="inline-flex items-center gap-1 text-xs font-medium text-status-rejected"
            >
              <AlertTriangle className="size-3.5" />
              {conflictCount}
            </span>
          )}
          <PlanStatusBadge status={plan.status} />
        </div>
      </div>

      {plan.blocks.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {plan.blocks.map((block) => (
            <li
              key={block.id}
              className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-muted px-3 py-1.5 text-xs"
            >
              <span className="font-medium text-text-primary">
                {block.leave_type_name || block.leave_type_code || "Leave"}
              </span>
              <span className="text-text-secondary">
                {formatDate(block.start_date)} → {formatDate(block.end_date)}
              </span>
              <span className={cn("text-text-muted")}>
                {block.working_days ?? "—"} days
              </span>
              <BlockStatusBadge status={block.status} className="ml-auto" />
            </li>
          ))}
        </ul>
      )}

      {footer && <div className="mt-3">{footer}</div>}

      <div className="mt-3 flex items-center gap-1 text-xs font-medium text-brand-primary">
        View plan
        <ChevronRight className="size-3.5" />
      </div>
    </Link>
  );
}