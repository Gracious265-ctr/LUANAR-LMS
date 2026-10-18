import Link from "next/link";

import type { Entitlement } from "@/lib/entitlements";
import { EmptyState } from "@/components/ui/states";
import { currentDateIso } from "@/lib/utils";
import { EditActionLink, EditIconButton } from "./edit-action-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

function isCurrentlyEffective(rule: Entitlement, today: string): boolean {
  return rule.effective_from <= today;
}

export function EntitlementTable({
  entitlements,
  today = currentDateIso(),
  onEdit,
}: {
  entitlements: Entitlement[];
  today?: string;
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
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
          <TableHead>Leave type</TableHead>
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
                  href={`/hr-admin/entitlements/${rule.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {rule.grade_start}–{rule.grade_end}
                </Link>
              </TableCell>
              <TableCell className="text-text-secondary">{rule.days} days</TableCell>
              <TableCell className="text-text-secondary">
                {rule.leave_type_name || "Annual (untyped)"}
              </TableCell>
              <TableCell className="text-text-secondary">
                {rule.effective_from}
              </TableCell>
              <TableCell>
                <Badge
                  size="sm"
                  tone={current ? "info" : "muted"}
                  className="font-medium"
                >
                  {current ? "Current" : "Scheduled"}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                {onEdit ? (
                  <EditIconButton
                    onClick={() => onEdit(rule.id)}
                    label={`Edit ${rule.grade_start}–${rule.grade_end}`}
                  />
                ) : (
                  <EditActionLink
                    href={`/hr-admin/entitlements/${rule.id}/edit`}
                  />
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}