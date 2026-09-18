import Link from "next/link";

import type { LeaveRule } from "@/lib/leave-rules";
import { leaveRuleStatus } from "@/lib/leave-rules";
import { currentDateIso } from "@/lib/utils";

export function LeaveRuleTable({
  rules,
  today = currentDateIso(),
}: {
  rules: LeaveRule[];
  today?: string;
}) {
  if (rules.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No leave rules found
        </p>
        <p className="mt-1 text-sm">
          Add a rule to define how long and under what conditions a leave type
          can be taken.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Leave type</th>
            <th className="py-3 pr-4">Max duration</th>
            <th className="py-3 pr-4">Min notice</th>
            <th className="py-3 pr-4">Document</th>
            <th className="py-3 pr-4">Annual</th>
            <th className="py-3 pr-4">Effective from</th>
            <th className="py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => {
            const current = leaveRuleStatus(rule, today) === "current";
            return (
              <tr
                key={rule.id}
                className="border-b border-border-default transition-colors hover:bg-surface-hover"
              >
                <td className="py-3 pr-4">
                  <Link
                    href={`/dashboard/hr-admin/leave-rules/${rule.id}/edit`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {rule.leave_type_name}
                  </Link>
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {rule.max_duration_days} days
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {rule.min_notice_days} days
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {rule.requires_supporting_document ? "Required" : "Not required"}
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {rule.consumes_annual_entitlement ? "Yes" : "No"}
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {rule.effective_from}
                </td>
                <td className="py-3">
                  <span
                    className={
                      current
                        ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                        : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                    }
                  >
                    {current ? "Current" : "Scheduled"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}