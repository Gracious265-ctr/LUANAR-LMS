"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Employee } from "@/lib/employees";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import { createRoleAssignment } from "@/lib/approver-roles-client";

/**
 * Grants an institution-wide role to one person.
 *
 * Only institution-wide, active roles get a holder here: a team role is staffed
 * on the Teams page, where the team and the role live together, and a retired
 * role receives no applications, so neither can be granted from here.
 *
 * Existing holders come from this role's assignments rather than from
 * `Employee.approver_roles`. Those codes are an aggregate over team membership
 * and institution-wide grants, so they cannot say which of the two a person
 * already has, and would wrongly hide somebody who can still be granted the
 * institution-wide holding.
 */
export function RoleAssignmentForm({
  role,
  employees,
  assignments = [],
}: {
  role: ApproverRole;
  employees: Employee[];
  /** This role's institution-wide holdings. */
  assignments?: RoleAssignment[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!role.is_institution_wide || !role.is_active) {
    return null;
  }

  const holderIds = new Set(assignments.map((assignment) => assignment.user));
  const candidates = employees.filter(
    (employee) => employee.is_active && !holderIds.has(employee.user_id)
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const user = String(formData.get("user") || "");

    if (!user) {
      setError("Choose somebody to hold this role.");
      setLoading(false);
      return;
    }

    try {
      await createRoleAssignment({ user: Number(user), role: role.id });
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

  if (candidates.length === 0) {
    return (
      <p className="mt-2 text-xs text-text-muted">
        {holderIds.size > 0
          ? "Every active employee already holds this role."
          : "No active employees are available."}
      </p>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-2 flex flex-wrap items-center gap-2"
    >
      <label className="sr-only" htmlFor={`holder-${role.id}`}>
        Add a holder of {role.label}
      </label>
      <select
        id={`holder-${role.id}`}
        name="user"
        className="min-w-44 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-xs text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
      >
        <option value="">Choose a person…</option>
        {candidates.map((employee) => (
          <option key={employee.id} value={employee.user_id}>
            {employee.full_name || employee.email}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={loading}
        className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Adding..." : "Add holder"}
      </button>
      {error && (
        <span className="text-xs text-status-rejected">{error}</span>
      )}
    </form>
  );
}
