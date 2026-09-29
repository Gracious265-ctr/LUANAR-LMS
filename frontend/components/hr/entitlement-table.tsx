import Link from "next/link";

import type { Entitlement } from "@/lib/entitlements";
import { EmptyState } from "@/components/ui/states";
import { currentDateIso } from "@/lib/utils";
import { EditActionLink } from "./edit-action-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
      <EmptyState
        title="No entitlement rules found"
        description="Add a grade range and annual leave entitlement to get started."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Grade range</TableHead>
          <TableHead>Annual days</TableHead>
          <TableHead>Effective from</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entitlements.map((rule) => {
          const current = isCurrentlyEffective(rule, today);
          return (
            <TableRow
              key={rule.id}
            >
              <TableCell>
                <Link
                  href={`/dashboard/hr-admin/entitlements/${rule.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {rule.grade_start}–{rule.grade_end}
                </Link>
              </TableCell>
              <TableCell className="text-text-secondary">{rule.days} days</TableCell>
              <TableCell className="text-text-secondary">
                {rule.effective_from}
              </TableCell>
              <TableCell>
                <span
                  className={
                    current
                      ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                      : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                  }
                >
                  {current ? "Current" : "Scheduled"}
                </span>
              </TableCell>
              <TableCell className="text-right">
                <EditActionLink
                  href={`/dashboard/hr-admin/entitlements/${rule.id}/edit`}
                />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}