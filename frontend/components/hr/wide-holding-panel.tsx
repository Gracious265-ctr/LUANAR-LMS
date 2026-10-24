"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ApproverRole } from "@/lib/approver-roles";
import {
  clearTeamManager,
  createCampusRoleAssignment,
  createRoleAssignment,
  createTeamRoleAssignment,
  removeCampusRoleAssignment,
  removeRoleAssignment,
  removeTeamRoleAssignment,
  setTeamManager,
} from "@/lib/approver-roles-client";
import { Badge } from "@/components/ui/badge";
import type { Employee, EmployeeCategory } from "@/lib/employees";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";

/** The three places a role may be held, narrowest first. */
export type WideScope = "institution" | "team" | "campus";

export const WIDE_SCOPE_LABELS: Record<WideScope, string> = {
  institution: "Institution-wide",
  team: "Team-wide",
  campus: "Campus-wide",
};

export function wideScopeLabel(scope: WideScope): string {
  return WIDE_SCOPE_LABELS[scope];
}

/**
 * One holding, whatever its scope: the role, the person, and the scope it is
 * held at. The shape is the same at all three levels on purpose, so one panel
 * can render and write all three.
 */
export interface WideHolding {
  id: number;
  role: number;
  user: number;
  user_name: string;
  role_label: string;
  /**
   * The team's single designated manager, on a team-wide holding only.
   *
   * A manager is a team-wide approver who additionally runs the team's own
   * members and workflow configuration, so the flag rides the holding rather
   * than the person and is written by HR through the set-manager action. The
   * campus and institution-wide scopes never carry it — there is nothing for
   * them to manage.
   */
  is_team_manager?: boolean;
}

/**
 * A team or campus the scope picker can offer.
 *
 * A team carries its category so the person list can follow the chosen team's
 * half of the institution; a campus is always academic, because every team at a
 * campus is an academic team.
 */
export interface ScopeOption {
  id: number;
  name: string;
  category?: EmployeeCategory;
}

/**
 * One scope's holders, and the form that changes them.
 *
 * The write is a pick-a-role, pick-a-person decision. At the team and campus
 * scopes saving a holder replaces the existing one for that role *at that
 * place* rather than failing — the form is "choose the role, choose the person
 * (and the scope where it is not the page's own)" rather than a list to append
 * to. HR is never asked to delete before they may change their mind, which is
 * why the role is chosen from a drop down instead of each role owning its own
 * save button. The institution scope is the exception this panel draws: a role
 * has exactly one institution-wide approver, so a role that already has an
 * institution holder is not offered to pick again — changing the holder there
 * is remove first, then assign, wherever the panel draws one.
 *
 * A wide approver is the same half of the institution they cover — the team's
 * category for a team holding, academic for a campus holding — so the person
 * list follows the fixed scope's category or, where the scope is chosen here,
 * the chosen option's. And a person holds only **one** wide approver role, so
 * once somebody is a wide approver anywhere they are gone from every other
 * wide-approver picker: the panel excludes the whole current holder list
 * (`excludedUserIds`), not just the people who already hold the role being
 * chosen.
 */
export function WideHoldingPanel({
  scope,
  roles,
  scopeOptions = [],
  scopeId: fixedScopeId,
  requiredCategory,
  employees,
  holdings,
  excludedUserIds = [],
  canManage = true,
}: {
  scope: WideScope;
  /** The roles that may be held at this scope, in the order to offer them. */
  roles: ApproverRole[];
  /** Teams or campuses to choose between. Empty for the institution-wide scope. */
  scopeOptions?: ScopeOption[];
  /**
   * The scope this panel already sits on — the team or campus whose page
   * renders it. No scope picker is drawn (there is nothing to choose), and the
   * id travels with the write. Replaces `scopeOptions`, which exists only
   * where a choice is real. Without either, a scoped write has no id to send.
   */
  scopeId?: number;
  /**
   * The category every holder here must be, for a fixed-scope panel: the team's
   * own category on a team page, academic on a campus page.
   */
  requiredCategory?: EmployeeCategory;
  employees: Employee[];
  holdings: WideHolding[];
  /**
   * Every wide approver, whatever their scope — the union of the institution,
   * team, and campus holdings. A person holds only one wide approver role, so
   * somebody who already holds one anywhere is not offered here: the panel
   * would create a person who reappears in another wide-approver section.
   */
  excludedUserIds?: number[];
  /**
   * Whether the viewer may write here. A team's manager reads this panel as a
   * statement of who its wide approvers are; assigning, removing, and
   * designating a manager stay HR's, so for a manager the panel draws no form
   * and no buttons — a read, not a form they could not save.
   */
  canManage?: boolean;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [roleId, setRoleId] = useState("");
  const [scopeValue, setScopeValue] = useState("");

  const needsScope = fixedScopeId == null && scopeOptions.length > 0;
  const chosenOption = scopeOptions.find(
    (option) => String(option.id) === scopeValue
  );
  const scopeCategory = requiredCategory ?? chosenOption?.category;
  // An institution-wide role has exactly one approver, so a role that already
  // has an institution holder is not offered to pick again: assigning it to a
  // different person is refused by the write, so the choice would be a save
  // that can only fail. Changing the holder there is remove first, then assign.
  // At a team or a campus the role stays offered — saving replaces that place's
  // own holder, and the other places keep theirs.
  const offerableRoles =
    scope === "institution"
      ? roles.filter(
          (role) => !holdings.some((holding) => holding.role === role.id)
        )
      : roles;
  const selectedRole = offerableRoles.find(
    (role) => String(role.id) === roleId
  );
  const excluded = new Set(excludedUserIds);

  // A holder is somebody with an employee record: the backend refuses to
  // appoint a user who has no record to hold the role with, so the picker does
  // not offer them and then apologise. The same half-of-the-institution rule
  // the write enforces is applied here, so the person offered is one the save
  // can actually accept — and anyone who already holds the chosen role here, or
  // holds a wide approver role anywhere at all, is a completed decision, not a
  // candidate for a second holding.
  const candidates =
    selectedRole == null
      ? []
      : employees.filter(
          (employee) =>
            employee.is_active &&
            !excluded.has(employee.user_id) &&
            (!scopeCategory || employee.category === scopeCategory) &&
            !holdings.some(
              (holding) =>
                holding.role === selectedRole.id &&
                holding.user === employee.user_id
            )
        );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);

    const formData = new FormData(event.currentTarget);
    const role = Number(formData.get("role") || 0);
    const user = Number(formData.get("user") || 0);
    const scopeId = Number(formData.get("scope_id") || 0) || fixedScopeId || 0;

    if (!role) {
      setError("Choose a role to assign.");
      setBusy(false);
      return;
    }
    if (!user) {
      setError("Choose somebody to hold this role.");
      setBusy(false);
      return;
    }
    // A scoped write without an id would travel as pk 0 and be refused by the
    // backend as a missing object; the scope is half the holding, so it is
    // named here rather than sent.
    if (scope !== "institution" && !scopeId) {
      setError(
        scope === "team"
          ? "Choose the team this holding applies to."
          : "Choose the campus this holding applies to."
      );
      setBusy(false);
      return;
    }

    try {
      // One write function per scope rather than a URL built here: the three
      // collections differ only in which id they take, and the client already
      // says so once.
      if (scope === "team") {
        await createTeamRoleAssignment({
          team: scopeId,
          role,
          user,
        });
      } else if (scope === "campus") {
        await createCampusRoleAssignment({
          campus: scopeId,
          role,
          user,
        });
      } else {
        await createRoleAssignment({ role, user });
      }
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

  async function handleRemove(holding: WideHolding) {
    setError("");
    setBusy(true);
    try {
      if (scope === "team") {
        await removeTeamRoleAssignment(holding.id);
      } else if (scope === "campus") {
        await removeCampusRoleAssignment(holding.id);
      } else {
        await removeRoleAssignment(holding.id);
      }
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

  /**
   * Designate, or undesignate, this holding as its team's manager.
   *
   * One manager per team: the backend clears the flag from the team's other
   * holders when a new one is set, so this is a per-holding "make this the
   * one" rather than a toggle that could leave the team with two. Only a
   * team-wide holding carries the flag, so this is drawn for the team scope
   * alone.
   */
  async function handleToggleManager(holding: WideHolding) {
    setError("");
    setBusy(true);
    try {
      if (holding.is_team_manager) {
        await clearTeamManager(holding.id);
      } else {
        await setTeamManager(holding.id);
      }
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
    <div className="rounded-lg border border-border-default bg-surface-page p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-text-primary">
          {canManage ? "Assign a wide approver" : "Wide approvers"}
        </h4>
        <span className="text-xs uppercase tracking-wide text-text-muted">
          {wideScopeLabel(scope)}
        </span>
      </div>

      {holdings.length > 0 && (
        <ul className="mt-3 space-y-1">
          {holdings.map((holding) => (
            <li
              key={holding.id}
              className="flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <span className="text-text-primary">
                <span className="font-medium">{holding.role_label}</span>
                {" · "}
                {holding.user_name}
                {holding.is_team_manager && (
                  <Badge size="sm" tone="info" className="ml-2">
                    Manager
                  </Badge>
                )}
              </span>
              {canManage && (
                <div className="flex items-center gap-2">
                  {scope === "team" && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleToggleManager(holding)}
                      className="rounded-md border border-border-default px-2 py-0.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {holding.is_team_manager
                        ? "Remove as manager"
                        : "Make manager"}
                    </button>
                  )}
                  <ConfirmButton
                  size="sm"
                  disabled={busy}
                  loading={busy}
                  onConfirm={() => handleRemove(holding)}
                  prompt={`Remove ${holding.user_name} as ${holding.role_label}?`}
                  aria-label={`Remove ${holding.user_name} from ${holding.role_label}`}
                >
                  Remove
                </ConfirmButton>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {holdings.length === 0 && (
        <p className="mt-2 text-xs text-text-muted">
          No holders here. A stage whose role is unheld falls back to the next
          scope, and is refused only when nothing is left to fall back to.
        </p>
      )}

      {!canManage ? (
        <p className="mt-2 text-xs text-text-muted">
          A team&apos;s wide approvers are assigned by HR. Ask HR to change who
          holds these.
        </p>
      ) : roles.length === 0 ? (
        <p className="mt-2 text-xs text-text-muted">
          No roles may be held at this scope right now.
        </p>
      ) : offerableRoles.length === 0 ? (
        <p className="mt-2 text-xs text-text-muted">
          Every active role already has its institution-wide holder. Remove a
          holder first to change it.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-3 space-y-2">
          <div>
            <label
              htmlFor={`role-${scope}`}
              className="mb-1 block text-xs font-medium text-text-secondary"
            >
              Role
            </label>
            <select
              id={`role-${scope}`}
              name="role"
              value={roleId}
              onChange={(event) => setRoleId(event.target.value)}
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            >
              <option value="">Choose a role…</option>
              {offerableRoles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>

          {needsScope && (
            <div>
              <label
                htmlFor={`scope-${scope}`}
                className="mb-1 block text-xs font-medium text-text-secondary"
              >
                {scope === "team" ? "Team" : "Campus"}
              </label>
              <select
                id={`scope-${scope}`}
                name="scope_id"
                value={scopeValue}
                onChange={(event) => setScopeValue(event.target.value)}
                className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              >
                <option value="">
                  {scope === "team"
                    ? "Choose a team…"
                    : "Choose a campus…"}
                </option>
                {scopeOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            {selectedRole != null && candidates.length === 0 ? (
              <p className="text-xs text-text-muted">
                Every active matching employee already holds a wide approver
                role here or elsewhere. Remove that holding first, or pick
                another role.
              </p>
            ) : (
              <>
                <label
                  htmlFor={`holder-${scope}`}
                  className="mb-1 block text-xs font-medium text-text-secondary"
                >
                  Person
                </label>
                <div className="flex flex-wrap gap-2">
                  <select
                    id={`holder-${scope}`}
                    name="user"
                    defaultValue=""
                    disabled={selectedRole == null}
                    className="min-w-44 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="">
                      {selectedRole == null
                        ? "Choose a role first…"
                        : "Choose a person…"}
                    </option>
                    {candidates.map((employee) => (
                      <option key={employee.id} value={employee.user_id}>
                        {employee.full_name || employee.email}
                      </option>
                    ))}
                  </select>
                  <Button
                    type="submit"
                    disabled={busy}
                    loading={busy}
                  >
                    Save holder
                  </Button>
                </div>
              </>
            )}
          </div>
          {error && <p className="text-xs text-status-rejected">{error}</p>}
        </form>
      )}
    </div>
  );
}