"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  deactivateApproverRole,
  historyScopeLabel,
  removeCampusRoleAssignment,
  removeRoleAssignment,
  removeTeamRoleAssignment,
} from "@/lib/approver-roles-client";
import { EditActionLink } from "./edit-action-link";

/**
 * Retires a role, or says why it cannot be retired yet.
 *
 * The backend is the authority here: it refuses while an active workflow, a
 * team, or a holder still needs the role, and names each one. Showing the
 * refusal beats hiding the control, because the blocker is something HR has to
 * go and fix.
 */
function RetireRoleButton({ role }: { role: ApproverRole }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!role.is_active) {
    // The state badge already says so; the cell just has nothing to offer.
    return null;
  }

  async function retire() {
    setBusy(true);
    setError("");
    try {
      await deactivateApproverRole(role.id);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={retire}
        disabled={busy}
        className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Retiring..." : "Retire"}
      </button>
      {error && (
        <span className="max-w-xs text-right text-xs text-status-rejected">
          {error}
        </span>
      )}
    </span>
  );
}

function RemoveHolderButton({
  onRemove,
  label,
}: {
  onRemove: () => Promise<void>;
  label: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await onRemove();
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      {error && <span className="text-xs text-status-rejected">{error}</span>}
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        aria-label={label}
        className="rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Removing..." : "Remove"}
      </button>
    </span>
  );
}

export function ApproverRoleTable({
  roles,
  assignments,
  teamHoldings,
  campusHoldings,
  teamNameById,
  campusNameById,
}: {
  roles: ApproverRole[];
  /**
   * Institution-wide holdings, keyed by role id. `undefined` means the page
   * could not load them — the column then says so rather than claiming a role
   * has no holder, which for a live role would be a costly lie.
   */
  assignments?: Record<number, RoleAssignment[]>;
  /** Team-wide holdings, keyed by role id. Absent means "none". */
  teamHoldings?: Record<number, TeamRoleAssignment[]>;
  /** Campus-wide holdings, keyed by role id. Absent means "none". */
  campusHoldings?: Record<number, CampusRoleAssignment[]>;
  /** Team names, keyed by team id, so a team-wide holder reads as a person. */
  teamNameById?: Record<number, string>;
  /** Campus names, keyed by campus id, so a campus-wide holder reads as a person. */
  campusNameById?: Record<number, string>;
}) {
  if (roles.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">No roles found</p>
        <p className="mt-1 text-sm">
          Create a role to give it to a team or to one person at institution,
          team or campus scope.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Role</th>
            <th className="py-3 pr-4">Code</th>
            <th className="py-3 pr-4">History visible</th>
            <th className="py-3 pr-4">Scope</th>
            <th className="py-3 pr-4">Holders</th>
            <th className="py-3 pr-4">State</th>
            <th className="py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {roles.map((role) => {
            const holders = assignments?.[role.id] ?? [];
            // A role's scope is where it is actually held, not a label that can
            // drift from it: an institution-wide role is held institution-wide,
            // a role with a campus-wide holder reads campus-wide, a role with a
            // team-wide holder reads team-wide, and only a role nobody holds
            // wide is a plain team role.
            const campus = campusHoldings?.[role.id] ?? [];
            const team = teamHoldings?.[role.id] ?? [];
            const scopeLabel = role.is_institution_wide
              ? "Institution-wide"
              : campus.length > 0
                ? "Campus-wide"
                : team.length > 0
                  ? "Team-wide"
                  : "Team role";
            return (
              <tr
                key={role.id}
                className="border-b border-border-default align-top transition-colors hover:bg-surface-hover"
              >
                <td className="py-3 pr-4">
                  <span className="block font-medium text-text-primary">
                    {role.label}
                  </span>
                  {role.description && (
                    <span className="block text-xs text-text-muted">
                      {role.description}
                    </span>
                  )}
                  {role.usage.length > 0 && (
                    <ul className="mt-1 space-y-0.5 text-xs text-text-muted">
                      {role.usage.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  )}
                </td>
                <td className="py-3 pr-4 font-mono text-xs text-text-secondary">
                  {role.code}
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {historyScopeLabel(role.history_scope)}
                </td>
                <td className="py-3 pr-4 text-text-secondary">{scopeLabel}</td>
                <td className="py-3 pr-4 text-text-secondary">
                  {role.is_institution_wide ? (
                    assignments === undefined ? (
                      <span className="text-text-muted">
                        Could not load the holders
                      </span>
                    ) : !role.is_active ? (
                      <span className="text-text-muted">
                        Retired — no longer routes applications
                      </span>
                    ) : holders.length === 0 ? (
                      <span className="text-status-rejected">
                        No holder — applications reaching this role have nobody to
                        approve
                      </span>
                    ) : (
                      <ul className="space-y-1">
                        {holders.map((assignment) => (
                          <li
                            key={assignment.id}
                            className="flex items-center gap-2"
                          >
                            <span>{assignment.user_name}</span>
                            <RemoveHolderButton
                              onRemove={() => removeRoleAssignment(assignment.id)}
                              label={`Remove ${assignment.user_name} from this role`}
                            />
                          </li>
                        ))}
                      </ul>
                    )
                  ) : campus.length + team.length === 0 ? (
                    <span className="text-text-muted">
                      Staffed through team membership
                    </span>
                  ) : (
                    <ul className="space-y-1">
                      {team.map((assignment) => {
                        const teamName =
                          teamNameById?.[assignment.team] ??
                          `Team #${assignment.team}`;
                        return (
                          <li
                            key={`team-${assignment.id}`}
                            className="flex items-center gap-2"
                          >
                            <span>
                              {assignment.user_name} — {teamName}
                            </span>
                            <RemoveHolderButton
                              onRemove={() =>
                                removeTeamRoleAssignment(assignment.id)
                              }
                              label={`Remove ${assignment.user_name} from the ${teamName} team`}
                            />
                          </li>
                        );
                      })}
                      {campus.map((assignment) => {
                        const campusName =
                          campusNameById?.[assignment.campus] ??
                          `Campus #${assignment.campus}`;
                        return (
                          <li
                            key={`campus-${assignment.id}`}
                            className="flex items-center gap-2"
                          >
                            <span>
                              {assignment.user_name} — {campusName}
                            </span>
                            <RemoveHolderButton
                              onRemove={() =>
                                removeCampusRoleAssignment(assignment.id)
                              }
                              label={`Remove ${assignment.user_name} from the ${campusName} campus`}
                            />
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </td>
                <td className="py-3 pr-4">
                  {role.is_active ? (
                    <span className="inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary">
                      Active
                    </span>
                  ) : (
                    <span className="inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted">
                      Retired
                    </span>
                  )}
                  {role.handles_cancellation && (
                    <span className="mt-1 block text-xs text-text-muted">
                      Decides cancellations
                    </span>
                  )}
                </td>
                <td className="py-3 text-right">
                  <span className="inline-flex items-center justify-end gap-2">
                    <EditActionLink
                      href={`/dashboard/hr-admin/roles/${role.id}/edit`}
                    />
                    <RetireRoleButton role={role} />
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
