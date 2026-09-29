"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";

import type { ApproverRole } from "@/lib/approver-roles";
import type {
  Workflow,
  WorkflowCategoryCode,
  WorkflowSectionInput,
} from "@/lib/workflows";
import { createWorkflow, updateWorkflow } from "@/lib/workflows-client";

export function WorkflowForm({
  workflow,
  roles,
  rolesError = "",
}: {
  workflow?: Workflow;
  roles: ApproverRole[];
  /** Set when the roles fetch failed; the form is unusable without its options. */
  rolesError?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(
    workflow?.effective_from ?? ""
  );
  const [isActive, setIsActive] = useState(workflow?.is_active ?? true);
  const [sections, setSections] = useState<WorkflowSectionInput[]>(
    workflow?.sections.map((section) => ({
      name: section.name,
      order: section.order,
      approver_role: section.approver_role,
      description: section.description,
      is_active: section.is_active,
    })) ??
      // A new workflow opens with one section, seeded with the first available
      // role rather than a hardcoded one.
      (roles.length > 0
        ? [
            {
              order: 1,
              name: "",
              approver_role: roles[0].code,
            },
          ]
        : [])
  );

  const baseHref = "/dashboard/hr-admin/workflows";
  const rolesUnavailable = rolesError !== "" || roles.length === 0;

  function move(index: number, direction: -1 | 1) {
    setSections((current) => {
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

  function update(index: number, patch: Partial<WorkflowSectionInput>) {
    setSections((current) =>
      current.map((section, i) => (i === index ? { ...section, ...patch } : section))
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    if (sections.length === 0) {
      setError("Add at least one approver section.");
      setLoading(false);
      return;
    }

    const input = {
      name: String(formData.get("name") || ""),
      employee_category: String(
        formData.get("employee_category") || ""
      ) as WorkflowCategoryCode,
      department: String(formData.get("department") || ""),
      effective_from: effectiveFrom || null,
      is_active: isActive,
      sections: sections.map((section, index) => ({
        order: index + 1,
        name: section.name.trim(),
        approver_role: section.approver_role,
        description: section.description?.trim(),
        is_active: section.is_active,
      })),
    };

    try {
      if (workflow) {
        await updateWorkflow(workflow.id, input);
      } else {
        await createWorkflow(input);
      }
      // Membership is edited on the Teams page, one section at a time, so a
      // whole-chain write never has to carry the roster.
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
              Approval sections
            </span>
            <p className="mt-1 text-xs text-text-muted">
              Every section is mandatory and runs in the order shown. A section
              is decided by whichever of its members acts first.
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              setSections((current) => [
                ...current,
                {
                  order: current.length + 1,
                  name: "",
                  approver_role: roles[0].code,
                },
              ])
            }
            disabled={rolesUnavailable}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            Add section
          </button>
        </div>

        {rolesError ? (
          <p className="mb-2 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {rolesError}
          </p>
        ) : sections.length === 0 ? (
          <p className="rounded-md bg-surface-muted p-3 text-sm text-text-secondary">
            No sections yet. Add at least one approver section.
          </p>
        ) : null}

        <div className="space-y-2">
          {sections.map((section, index) => (
            <div
              key={index}
              className="rounded-md border border-border-default bg-surface-card p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="grid size-8 shrink-0 place-content-center rounded-full bg-brand-primary-subtle text-sm font-semibold text-brand-primary">
                  {index + 1}
                </span>
                <input
                  aria-label={`Section ${index + 1} name`}
                  value={section.name}
                  onChange={(event) => update(index, { name: event.target.value })}
                  placeholder="e.g. Supervisor"
                  className="min-w-36 flex-1 rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
                />
                <select
                  aria-label={`Section ${index + 1} approver`}
                  value={section.approver_role}
                  disabled={rolesUnavailable}
                  onChange={(event) =>
                    update(index, { approver_role: event.target.value })
                  }
                  className="min-w-44 flex-1 rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {section.approver_role &&
                    !roles.some((role) => role.code === section.approver_role) && (
                      <option value={section.approver_role}>
                        {section.approver_role} (no longer active)
                      </option>
                    )}
                  {roles.map((role) => (
                    <option key={role.code} value={role.code}>
                      {role.label}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    aria-label={`Move section ${index + 1} up`}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                    className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Move section ${index + 1} down`}
                    disabled={index === sections.length - 1}
                    onClick={() => move(index, 1)}
                    className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ArrowDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove section ${index + 1}`}
                    onClick={() =>
                      setSections((current) =>
                        current.filter((_, i) => i !== index)
                      )
                    }
                    className="grid size-8 place-content-center rounded-md border border-border-default text-status-rejected hover:bg-surface-hover"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2 pl-10">
                <label className="flex items-center gap-1.5 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={section.is_active ?? true}
                    onChange={(event) =>
                      update(index, { is_active: event.target.checked })
                    }
                    className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
                  />
                  Active section
                </label>

                {workflow && (
                  <SectionMembers
                    sectionId={savedSectionIds(workflow, section, index)}
                    count={savedSectionIds(workflow, section, index) ? matchedCount(workflow, section, index) : 0}
                  />
                )}
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
          disabled={loading || rolesUnavailable || sections.length === 0}
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

/**
 * The section id a form row maps back to, when saving an existing workflow.
 * The id is keyed to the queued row, not the array index, so a reorder keeps
 * each roster editor pointed at the same section. A row whose (role, name)
 * pair has no saved match yet is a step that does not exist in the backend.
 */
function savedSectionIds(
  workflow: Workflow,
  section: WorkflowSectionInput,
  index: number
): number | null {
  if (!workflow) {
    return null;
  }
  const saved = workflow.sections.filter(
    (s) => s.name === section.name && s.approver_role === section.approver_role
  );
  // The very first time a name/role pair appears it is the row's own; a repeat
  // is a fresh step with no saved id yet.
  return saved[index]?.id ?? null;
}

function matchedCount(
  workflow: Workflow,
  section: WorkflowSectionInput,
  index: number
): number {
  if (!workflow) {
    return 0;
  }
  const saved = workflow.sections.filter(
    (s) => s.name === section.name && s.approver_role === section.approver_role
  );
  return saved[index]?.member_count ?? 0;
}

/** Read-only member count for a saved section of the chain being edited. */
function SectionMembers({
  sectionId,
  count,
}: {
  sectionId: number | null;
  count: number;
}) {
  return (
    <span className="text-xs text-text-muted">
      {sectionId
        ? `${count} member${count === 1 ? "" : "s"}`
        : "A saved section is staffed by its members, which are added on the Teams page."}
    </span>
  );
}