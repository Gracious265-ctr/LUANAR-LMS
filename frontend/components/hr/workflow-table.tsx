import Link from "next/link";

import type { Workflow } from "@/lib/workflows";
import { EmptyState } from "@/components/ui/states";
import {
  approverRoleLabel,
  workflowCategoryLabel,
  workflowStateBadgeClass,
  workflowStateLabel,
} from "@/lib/workflows";

import { EditActionLink } from "./edit-action-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function scopeLabel(workflow: Workflow): string {
  const category = workflowCategoryLabel(workflow.employee_category);
  return workflow.department
    ? `${category} / ${workflow.department}`
    : category;
}

export function WorkflowTable({ workflows }: { workflows: Workflow[] }) {
  if (workflows.length === 0) {
    return (
      <EmptyState
        title="No workflows found"
        description="Create a workflow to define the approval sequence for a category or department."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Scope</TableHead>
          <TableHead>Effective from</TableHead>
          <TableHead>State</TableHead>
          <TableHead>Approval sequence</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {workflows.map((workflow) => (
          <TableRow
            key={workflow.id}
          >
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/workflows/${workflow.id}/edit`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {workflow.name}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">
              {scopeLabel(workflow)}
            </TableCell>
            <TableCell className="text-text-secondary">
              {workflow.effective_from || "—"}
            </TableCell>
            <TableCell>
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${workflowStateBadgeClass(workflow.state)}`}
              >
                {workflowStateLabel(workflow.state)}
              </span>
            </TableCell>
            <TableCell className="text-text-secondary">
              {workflow.stages
                .map((stage) => approverRoleLabel(stage.approver_role))
                .join(" → ")}
            </TableCell>
            <TableCell className="text-right">
              <EditActionLink
                href={`/dashboard/hr-admin/workflows/${workflow.id}/edit`}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}