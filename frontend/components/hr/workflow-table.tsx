import Link from "next/link";

import type { Workflow } from "@/lib/workflows";
import {
  approverRoleLabel,
  workflowCategoryLabel,
  workflowStateBadgeClass,
  workflowStateLabel,
} from "@/lib/workflows";

import { EditActionLink } from "./edit-action-link";

function scopeLabel(workflow: Workflow): string {
  const category = workflowCategoryLabel(workflow.employee_category);
  return workflow.department
    ? `${category} / ${workflow.department}`
    : category;
}

export function WorkflowTable({ workflows }: { workflows: Workflow[] }) {
  if (workflows.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No workflows found
        </p>
        <p className="mt-1 text-sm">
          Create a workflow to define the approval sequence for a
          category or department.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Name</th>
            <th className="py-3 pr-4">Scope</th>
            <th className="py-3 pr-4">Effective from</th>
            <th className="py-3 pr-4">State</th>
            <th className="py-3 pr-4">Approval sequence</th>
            <th className="py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {workflows.map((workflow) => (
            <tr
              key={workflow.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/workflows/${workflow.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {workflow.name}
                </Link>
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {scopeLabel(workflow)}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {workflow.effective_from || "—"}
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${workflowStateBadgeClass(workflow.state)}`}
                >
                  {workflowStateLabel(workflow.state)}
                </span>
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {workflow.stages
                  .map((stage) => approverRoleLabel(stage.approver_role))
                  .join(" → ")}
              </td>
              <td className="py-3 text-right">
                <EditActionLink
                  href={`/dashboard/hr-admin/workflows/${workflow.id}/edit`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}