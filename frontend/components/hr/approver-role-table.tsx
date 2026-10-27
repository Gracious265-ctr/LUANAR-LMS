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
import { Badge } from "@/components/ui/badge";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EditActionLink, EditIconButton } from "./edit-action-link";

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
      <ConfirmButton
        size="sm"
        onConfirm={retire}
        loading={busy}
        prompt={`Retire ${role.label}?`}
      >
        Retire
      </ConfirmButton>
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
      <ConfirmButton
        size="sm"
        onConfirm={remove}
        loading={busy}
        aria-label={label}
      >
        Remove
      </ConfirmButton>
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
  onEdit,
  empty,
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
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
  /** Overrides the empty state — the section supplies search-aware copy. */
  empty?: React.ReactNode;
}) {
  if (roles.length === 0) {
    return (
      empty ?? (
        <EmptyState
          title="No roles found"
          description="Create a role to give it to a team or to one person at institution, team or campus scope."
        />
      )
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Role</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>History visible</TableHead>
          <TableHead>Scope</TableHead>
          <TableHead>Holders</TableHead>
          <TableHead>State</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
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
            <TableRow key={role.id} className="align-top">
              <TableCell>
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
              </TableCell>
              <TableCell className="font-mono text-xs text-text-secondary">
                {role.code}
              </TableCell>
              <TableCell className="text-text-secondary">
                {historyScopeLabel(role.history_scope)}
              </TableCell>
              <TableCell className="text-text-secondary">{scopeLabel}</TableCell>
              <TableCell className="text-text-secondary">
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
              </TableCell>
              <TableCell>
                {role.is_active ? (
                  <Badge size="sm" tone="info">
                    Active
                  </Badge>
                ) : (
                  <Badge size="sm" tone="muted">
                    Retired
                  </Badge>
                )}
                {role.handles_cancellation && (
                  <span className="mt-1 block text-xs text-text-muted">
                    Decides cancellations
                  </span>
                )}
              </TableCell>
              <TableCell className="text-right">
                <span className="inline-flex items-center justify-end gap-2">
                  {onEdit ? (
                    <EditIconButton
                      onClick={() => onEdit(role.id)}
                      label={`Edit ${role.label}`}
                    />
                  ) : (
                    <EditActionLink
                      href={`/dashboard/hr-admin/roles/${role.id}/edit`}
                    />
                  )}
                  <RetireRoleButton role={role} />
                </span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
