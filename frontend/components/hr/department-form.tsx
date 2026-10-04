"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Department } from "@/lib/departments";
import {
  createDepartment,
  retireDepartment,
  updateDepartment,
} from "@/lib/departments-client";

/** Where the standalone form returns to, and what Cancel links back to. */
const LIST_ROUTE = "/dashboard/hr-admin/departments";

/**
 * A department is a name and nothing else.
 *
 * The name is what makes "the ICT team" and "the ICT approvers" mean one unit
 * rather than a string HR typed twice. It is also the only thing HR sets here:
 * the teams and employees inside it are relationships those rows own, so they
 * are shown, not edited.
 */
export function DepartmentForm({
  department,
  onSuccess,
  onCancel,
}: {
  department?: Department;
  /**
   * Replaces the default `router.push(listRoute)` + `router.refresh()`. The
   * overlay passes this so it can close itself and refetch; with it omitted the
   * form navigates on its own, which is what a standalone page needs.
   *
   * Retirement reports through here too: it is the same write with the same
   * consequence for the list, so it does not need its own escape hatch.
   */
  onSuccess?: (department: Department) => void;
  /** Adds a dismiss action. An inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  /** Close-and-refresh when hosted, navigate when standalone. */
  function done(saved: Department) {
    if (onSuccess) {
      onSuccess(saved);
      return;
    }
    router.push(LIST_ROUTE);
    router.refresh();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const name = String(new FormData(event.currentTarget).get("name") || "");

    try {
      const saved = department
        ? await updateDepartment(department.id, { name })
        : await createDepartment({ name });
      done(saved);
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

  async function handleRetire() {
    if (!department) return;
    setError("");
    setLoading(true);
    try {
      done(await retireDepartment(department.id));
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="name"
          name="name"
          required
          maxLength={200}
          defaultValue={department?.name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. ICT"
        />
        <p className="mt-1 text-xs text-text-muted">
          Teams are placed in a department and an employee&apos;s department
          decides which team&apos;s approvers they may become.
        </p>
      </div>

      {department ? (
        <div className="rounded-md border border-border-default bg-surface-muted p-3 text-sm text-text-secondary">
          <p>
            {department.team_count} team
            {department.team_count === 1 ? "" : "s"} ·{" "}
            {department.employee_count} employee
            {department.employee_count === 1 ? "" : "s"}
          </p>
        </div>
      ) : null}

      {error && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading
            ? "Saving..."
            : department
              ? "Save changes"
              : "Create department"}
        </button>
        {department ? (
          <button
            type="button"
            onClick={handleRetire}
            disabled={loading}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-status-rejected hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            Retire department
          </button>
        ) : null}
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </button>
        ) : (
          <Link
            href={LIST_ROUTE}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
