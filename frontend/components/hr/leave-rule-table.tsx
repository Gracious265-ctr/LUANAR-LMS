import Link from "next/link";

import type { LeaveRule } from "@/lib/leave-rules";
import { leaveRuleStatus } from "@/lib/leave-rules-client";
import { currentDateIso } from "@/lib/utils";
import { EditActionLink, EditIconButton } from "./edit-action-link";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function LeaveRuleTable({
  rules,
  today = currentDateIso(),
  onEdit,
}: {
  rules: LeaveRule[];
  today?: string;
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (rules.length === 0) {
    return (
      <EmptyState
        title="No leave rules found"
        description="Add a rule to define how long and under what conditions a leave type can be taken."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Leave type</TableHead>
          <TableHead>Max duration</TableHead>
          <TableHead>Min notice</TableHead>
          <TableHead>Document</TableHead>
          <TableHead>Annual</TableHead>
          <TableHead>Effective from</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rules.map((rule) => {
          const current = leaveRuleStatus(rule, today) === "current";
          return (
            <TableRow
              key={rule.id}
            >
              <TableCell>
                <Link
                  href={`/dashboard/hr-admin/leave-rules/${rule.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {rule.leave_type_name}
                </Link>
              </TableCell>
              <TableCell className="text-text-secondary">
                {rule.max_duration_days} days
              </TableCell>
              <TableCell className="text-text-secondary">
                {rule.min_notice_days} days
              </TableCell>
              <TableCell className="text-text-secondary">
                {rule.requires_supporting_document ? "Required" : "Not required"}
              </TableCell>
              <TableCell className="text-text-secondary">
                {rule.consumes_annual_entitlement ? "Yes" : "No"}
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
                    label={`Edit ${rule.leave_type_name} rule`}
                  />
                ) : (
                  <EditActionLink
                    href={`/dashboard/hr-admin/leave-rules/${rule.id}/edit`}
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