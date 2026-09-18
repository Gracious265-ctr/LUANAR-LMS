import Link from "next/link";

import type { Delegation } from "@/lib/delegations";
import {
  delegationStateBadgeClass,
  delegationStateLabel,
} from "@/lib/delegations";

function periodLabel(delegation: Delegation): string {
  return delegation.ends_on
    ? `${delegation.starts_on} \u2192 ${delegation.ends_on}`
    : `From ${delegation.starts_on} (open-ended)`;
}

export function DelegationTable({
  delegations,
}: {
  delegations: Delegation[];
}) {
  if (delegations.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No delegations found
        </p>
        <p className="mt-1 text-sm">
          Create a delegation request when an approver will be unavailable so HR
          can route their approvals to a delegate.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Approver</th>
            <th className="py-3 pr-4">Delegate</th>
            <th className="py-3 pr-4">Period</th>
            <th className="py-3">State</th>
          </tr>
        </thead>
        <tbody>
          {delegations.map((delegation) => (
            <tr
              key={delegation.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/delegations/${delegation.id}`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {delegation.approver_name}
                </Link>
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {delegation.delegate_name || "Not yet assigned"}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {periodLabel(delegation)}
              </td>
              <td className="py-3">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${delegationStateBadgeClass(delegation.state)}`}
                >
                  {delegationStateLabel(delegation.state)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}