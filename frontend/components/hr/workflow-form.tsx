"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";

import type {
  ApproverRoleCode,
  Workflow,
  WorkflowCategoryCode,
  WorkflowStageInput,
} from "@/lib/workflows";
import {
  APPROVER_ROLE_CODES,
  APPROVER_ROLE_LABELS,
  createWorkflow,
  updateWorkflow,
} from "@/lib/workflows-client";

const DEFAULT_FIRST_ROLE: ApproverRoleCode = "supervisor";

export function WorkflowForm({
  workflow,
}: {
  workflow?: Workflow;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(
    workflow?.effective_from ?? ""
  );
  const [isActive, setIsActive] = useState(workflow?.is_active ?? true);
  const [stages, setStages] = useState<WorkflowStageInput[]>(
    workflow?.stages.map((stage) => ({
      order: stage.order,
      approver_role: stage.approver_role,
    })) ?? [{ order: 1, approver_role: DEFAULT_FIRST_ROLE }]
  );

  const baseHref = "/dashboard/hr-admin/workflows";

  function moveStage(index: number, direction: -1 | 1) {
    setStages((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) {
        return current;
      }
      const next = [...current];
      const [moved] = next.splice(index, 1);
      next.splice(target, 0, moved);
      return next;
    });
  }

  function removeStage(index: number) {
    setStages((current) => current.filter((_, i) => i !== index));
  }

  function updateRole(index: number, role: ApproverRoleCode) {
    setStages((current) =>
      current.map((stage, i) =>
        i === index ? { ...stage, approver_role: role } : stage
      )
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    try {
      const input = {
        name: String(formData.get("name") || ""),
        employee_category: String(
          formData.get("employee_category") || ""
        ) as WorkflowCategoryCode,
        department: String(formData.get("department") || ""),
        effective_from: effectiveFrom || null,
        is_active: isActive,
        stages: stages.map((stage, index) => ({
          order: index + 1,
          approver_role: stage.approver_role,
        })),
      };
      if (workflow) {
        await updateWorkflow(workflow.id, input);
      } else {
        await createWorkflow(input);
      }
      router.push(baseHref);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <label
          htmlFor="name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Workflow name
        </label>
        <input
          id="name"
          name="name"
          type="text"
          required
          defaultValue={workflow?.name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="employee_category"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Employee category
        </label>
        <select
          id="employee_category"
          name="employee_category"
          defaultValue={workflow?.employee_category ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">Any category</option>
          <option value="academic">Academic</option>
          <option value="administration">Administration</option>
        </select>
        <p className="mt-1 text-xs text-text-muted">
          Blank applies the workflow to every employee category.
        </p>
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="department"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Department / Faculty
        </label>
        <input
          id="department"
          name="department"
          type="text"
          defaultValue={workflow?.department}
          placeholder="e.g. Faculty of Science"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Blank applies the workflow to every department.
        </p>
      </div>

      <div>
        <label
          htmlFor="effective_from"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Effective from
        </label>
        <input
          id="effective_from"
          name="effective_from"
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Leave blank to keep this workflow a draft.
        </p>
      </div>

      {effectiveFrom && (
        <div>
          <label
            htmlFor="is_active"
            className="mb-1 flex items-center gap-2 text-sm font-medium text-text-primary"
          >
            <input
              id="is_active"
              name="is_active"
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              className="size-4 rounded border-input-border text-brand-primary focus:ring-2 focus:ring-input-ring-focus"
            />
            Active
          </label>
          <p className="mt-1 text-xs text-text-muted">
            Only active workflows apply. Deactivating frees the scope for a
            replacement.
          </p>
        </div>
      )}

      <div className="md:col-span-2">
        <div className="mb-2 flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-text-primary">
              Approval stages
            </span>
            <p className="mt-1 text-xs text-text-muted">
              Every stage is mandatory and runs in the order shown.
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              setStages((current) => [
                ...current,
                {
                  order: current.length + 1,
                  approver_role: DEFAULT_FIRST_ROLE,
                },
              ])
            }
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            <Plus className="h-4 w-4" />
            Add stage
          </button>
        </div>

        {stages.length === 0 && (
          <p className="rounded-md bg-surface-muted p-3 text-sm text-text-secondary">
            No stages yet. Add at least one approver role.
          </p>
        )}

        <div className="space-y-2">
          {stages.map((stage, index) => (
            <div
              key={index}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border-default bg-surface-card p-3"
            >
              <span className="grid size-8 shrink-0 place-content-center rounded-full bg-brand-primary-subtle text-sm font-semibold text-brand-primary">
                {index + 1}
              </span>
              <select
                aria-label={`Stage ${index + 1} approver`}
                value={stage.approver_role}
                onChange={(event) =>
                  updateRole(index, event.target.value as ApproverRoleCode)
                }
                className="min-w-44 flex-1 rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              >
                {APPROVER_ROLE_CODES.map((code) => (
                  <option key={code} value={code}>
                    {APPROVER_ROLE_LABELS[code]}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  aria-label={`Move stage ${index + 1} up`}
                  disabled={index === 0}
                  onClick={() => moveStage(index, -1)}
                  className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label={`Move stage ${index + 1} down`}
                  disabled={index === stages.length - 1}
                  onClick={() => moveStage(index, 1)}
                  className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ArrowDown className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label={`Remove stage ${index + 1}`}
                  onClick={() => removeStage(index)}
                  className="grid size-8 place-content-center rounded-md border border-border-default text-status-rejected hover:bg-surface-hover"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : workflow ? "Save changes" : "Create workflow"}
        </button>
        <Link
          href={baseHref}
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}