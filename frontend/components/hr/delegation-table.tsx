import Link from "next/link";

// The type comes from the server-safe module, but the helpers must come from
// the client-safe one: this table is rendered inside the client-side approvals
// workspace, and `@/lib/delegations` re-exports the API client, which reads
// `next/headers` and cannot cross into the browser bundle.
import type { Delegation } from "@/lib/delegations";
import {
  delegationStateBadgeClass,
  delegationStateLabel,
} from "@/lib/delegations-client";

function periodLabel(delegation: Delegation): string {
  return delegation.ends_on
    ? `${delegation.starts_on} \u2192 ${delegation.ends_on}`
    : `From ${delegation.starts_on} (open-ended)`;
}

export function DelegationTable({
  delegations,
  baseHref = "/dashboard/hr-admin/delegations",
  emptyHint = "Create a delegation request when an approver will be unavailable so HR can route their approvals to a delegate.",
}: {
  delegations: Delegation[];
  /** Where a row's name links to — the approver's own view lives elsewhere. */
  baseHref?: string;
  emptyHint?: string;
}) {
  if (delegations.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No delegations found
        </p>
        <p className="mt-1 text-sm">{emptyHint}</p>
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
                  href={`${baseHref}/${delegation.id}`}
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