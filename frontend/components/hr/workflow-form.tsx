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
import { Field, Input, Select } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

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
      <Field label="Workflow name" htmlFor="name">
        <Input
          id="name"
          name="name"
          type="text"
          required
          defaultValue={workflow?.name}
        />
      </Field>

      <Field
        label="Employee category"
        htmlFor="employee_category"
        hint="Blank applies the workflow to every employee category."
      >
        <Select
          id="employee_category"
          name="employee_category"
          defaultValue={workflow?.employee_category ?? ""}
        >
          <option value="">Any category</option>
          <option value="academic">Academic</option>
          <option value="administration">Administration</option>
        </Select>
      </Field>

      <Field
        label="Department / Faculty"
        htmlFor="department"
        hint="Blank applies the workflow to every department."
        className="md:col-span-2"
      >
        <Input
          id="department"
          name="department"
          type="text"
          defaultValue={workflow?.department}
          placeholder="e.g. Faculty of Science"
        />
      </Field>

      <Field
        label="Effective from"
        htmlFor="effective_from"
        hint="Leave blank to keep this workflow a draft."
      >
        <Input
          id="effective_from"
          name="effective_from"
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
        />
      </Field>

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
              <Select
                aria-label={`Stage ${index + 1} approver`}
                value={stage.approver_role}
                onChange={(event) =>
                  updateRole(index, event.target.value as ApproverRoleCode)
                }
                className="w-auto min-w-44 flex-1"
              >
                {APPROVER_ROLE_CODES.map((code) => (
                  <option key={code} value={code}>
                    {APPROVER_ROLE_LABELS[code]}
                  </option>
                ))}
              </Select>
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
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : workflow ? "Save changes" : "Create workflow"}
        </Button>
        <Link
          href={baseHref}
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}