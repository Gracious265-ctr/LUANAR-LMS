import Link from "next/link";

// The type comes from the server-safe module, but the helpers must come from
// the client-safe one: this table is rendered inside the client-side approvals
// workspace, and `@/lib/delegations` re-exports the API client, which reads
// `next/headers` and cannot cross into the browser bundle.
import type { Delegation } from "@/lib/delegations";
import { EmptyState } from "@/components/ui/states";
import {
  delegationStateTone,
  delegationStateLabel,
} from "@/lib/delegations-client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

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
      <EmptyState title="No delegations found" description={emptyHint} />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Approver</TableHead>
          <TableHead>Delegate</TableHead>
          <TableHead>Period</TableHead>
          <TableHead>State</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {delegations.map((delegation) => (
          <TableRow
            key={delegation.id}
          >
            <TableCell>
              <Link
                href={`${baseHref}/${delegation.id}`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {delegation.approver_name}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">
              {delegation.delegate_name || "Not yet assigned"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {periodLabel(delegation)}
            </TableCell>
            <TableCell>
              <Badge
                size="sm"
                tone={delegationStateTone(delegation.state)}
                className="font-medium"
              >
                {delegationStateLabel(delegation.state)}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}