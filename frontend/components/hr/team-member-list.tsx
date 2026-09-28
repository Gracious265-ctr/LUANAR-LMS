"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Employee } from "@/lib/employees";
import type { Team } from "@/lib/teams";
import { addTeamMember, removeTeamMember } from "@/lib/teams-client";

/**
 * Staffs one role on one team.
 *
 * The options are the roles the team's own workflow asks for — an approver who
 * is not named in any stage of that chain would never be asked to approve
 * anything, so offering them would be misleading.
 */
export function TeamMemberList({
  team,
  employees,
}: {
  team: Team;
  employees: Employee[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  const activeEmployees = employees.filter((employee) => employee.is_active);

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(0);

    const formData = new FormData(event.currentTarget);
    const user = String(formData.get("user") || "");
    const role = String(formData.get("role") || "");

    if (!user || !role) {
      setError("Choose a person and the role they hold on this team.");
      setBusy(null);
      return;
    }

    try {
      await addTeamMember({ team: team.id, user: Number(user), role });
      setAdding(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  async function remove(memberId: number) {
    setError("");
    setBusy(memberId);
    try {
      await removeTeamMember(memberId);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  const noChain = team.stage_roles.length === 0;

  return (
    <div className="mt-3">
      {team.members.length === 0 ? (
        <p className="text-sm text-text-muted">
          Nobody is on this team yet. An application routed here would have
          nobody to approve it.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {team.members.map((member) => (
            <li
              key={member.id}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border-default bg-surface-card px-3 py-2 text-sm"
            >
              <span className="font-medium text-text-primary">
                {member.user_name}
              </span>
              <span className="text-text-muted">as {member.role_label}</span>
              <button
                type="button"
                onClick={() => remove(member.id)}
                disabled={busy === member.id}
                aria-label={`Remove ${member.user_name} from this team`}
                className="ml-auto rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === member.id ? "Removing..." : "Remove"}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p className="mt-2 text-sm text-status-rejected">{error}</p>
      )}

      {noChain ? (
        <p className="mt-2 text-xs text-text-muted">
          This team&apos;s workflow names no approver roles, so there is nobody
          to staff. Point the team at a workflow with stages first.
        </p>
      ) : adding ? (
        <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor={`member-user-${team.id}`}>
            Add a member to {team.name}
          </label>
          <select
            id={`member-user-${team.id}`}
            name="user"
            className="min-w-44 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          >
            <option value="">Choose a person…</option>
            {activeEmployees.map((employee) => (
              <option key={employee.id} value={employee.user_id}>
                {employee.full_name || employee.email}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor={`member-role-${team.id}`}>
            The role they hold on {team.name}
          </label>
          <select
            id={`member-role-${team.id}`}
            name="role"
            className="min-w-40 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          >
            <option value="">As…</option>
            {team.stage_roles.map((role) => (
              <option key={role.code} value={role.code}>
                {role.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy === 0}
            className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === 0 ? "Adding..." : "Add"}
          </button>
          <button
            type="button"
            onClick={() => setAdding(false)}
            className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="mt-3 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Add a member
        </button>
      )}

      {/* One member per role: the backend refuses a second holder of a role
          this team already has, naming the person who holds it. */}
      <p className="mt-2 text-xs text-text-muted">
        One person per role — this team&apos;s workflow names{" "}
        {team.stage_roles.length} role{team.stage_roles.length === 1 ? "" : "s"}.
      </p>
    </div>
  );
}
