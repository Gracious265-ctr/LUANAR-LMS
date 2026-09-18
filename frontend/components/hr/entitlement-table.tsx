import Link from "next/link";

import type { Entitlement } from "@/lib/entitlements";
import { currentDateIso } from "@/lib/utils";

function isCurrentlyEffective(rule: Entitlement, today: string): boolean {
  return rule.effective_from <= today;
}

export function EntitlementTable({
  entitlements,
  today = currentDateIso(),
}: {
  entitlements: Entitlement[];
  today?: string;
}) {
  if (entitlements.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No entitlement rules found
        </p>
        <p className="mt-1 text-sm">
          Add a grade range and annual leave entitlement to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Grade range</th>
            <th className="py-3 pr-4">Annual days</th>
            <th className="py-3 pr-4">Effective from</th>
            <th className="py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {entitlements.map((rule) => {
            const current = isCurrentlyEffective(rule, today);
            return (
              <tr
                key={rule.id}
                className="border-b border-border-default transition-colors hover:bg-surface-hover"
              >
                <td className="py-3 pr-4">
                  <Link
                    href={`/dashboard/hr-admin/entitlements/${rule.id}/edit`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {rule.grade_start}–{rule.grade_end}
                  </Link>
                </td>
                <td className="py-3 pr-4 text-text-secondary">{rule.days} days</td>
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