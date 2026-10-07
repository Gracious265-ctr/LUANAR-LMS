"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ApproverRole } from "@/lib/approver-roles";
import {
  createCampusRoleAssignment,
  createRoleAssignment,
  createTeamRoleAssignment,
  removeCampusRoleAssignment,
  removeRoleAssignment,
  removeTeamRoleAssignment,
} from "@/lib/approver-roles-client";
import type { Employee, EmployeeCategory } from "@/lib/employees";

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
 * One role's holders at one scope, and the form that changes them.
 *
 * Saving a second holder replaces the first rather than failing, so the form is
 * "pick the person" rather than "add to a list" — there is never more than one
 * holder to manage, and HR is never asked to delete before they may change
 * their mind. A scope picker appears only where the scope is chosen per
 * holding: an institution-wide role has no scope to choose.
 *
 * A wide approver is the same half of the institution they cover — the team's
 * category for a team holding, academic for a campus holding — so the person
 * list is scoped to the fixed scope's category or, where the scope is chosen
 * here, to the chosen option's.
 */
export function WideHoldingPanel({
  role,
  scope,
  scopeOptions = [],
  scopeId: fixedScopeId,
  requiredCategory,
  employees,
  holdings,
}: {
  role: ApproverRole;
  scope: WideScope;
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
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [scopeValue, setScopeValue] = useState("");

  const needsScope = fixedScopeId == null && scopeOptions.length > 0;
  const chosenOption = scopeOptions.find(
    (option) => String(option.id) === scopeValue
  );
  const scopeCategory = requiredCategory ?? chosenOption?.category;

  // A holder is somebody with an employee record: the backend refuses to
  // appoint a user who has no record to hold the role with, so the picker does
  // not offer them and then apologise. The same half-of-the-institution rule
  // the write enforces is applied here, so the person offered is one the save
  // can actually accept.
  const candidates = employees.filter(
    (employee) =>
      employee.is_active &&
      (!scopeCategory || employee.category === scopeCategory) &&
      !holdings.some((h) => h.user === employee.user_id)
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);

    const formData = new FormData(event.currentTarget);
    const user = Number(formData.get("user") || 0);
    const scopeId = Number(formData.get("scope_id") || 0) || fixedScopeId || 0;

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
          role: role.id,
          user,
        });
      } else if (scope === "campus") {
        await createCampusRoleAssignment({
          campus: scopeId,
          role: role.id,
          user,
        });
      } else {
        await createRoleAssignment({ role: role.id, user });
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

  return (
    <div className="rounded-lg border border-border-default bg-surface-page p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-text-primary">{role.label}</h4>
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
              <span className="text-text-primary">{holding.user_name}</span>
              <button
                type="button"
                disabled={busy}
                onClick={() => handleRemove(holding)}
                className="rounded-md border border-border-default px-2 py-0.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {holdings.length === 0 && (
        <p className="mt-2 text-xs text-text-muted">
          No holder. A stage whose role is unheld falls back to the next scope,
          and is refused only when nothing is left to fall back to.
        </p>
      )}

      {candidates.length === 0 ? (
        <p className="mt-2 text-xs text-text-muted">
          {holdings.length > 0
            ? "Every active employee with an employee record already holds this role."
            : "No active employees are available to hold this role."}
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-3 space-y-2">
          {needsScope && (
            <div>
              <label
                htmlFor={`scope-${role.id}-${scope}`}
                className="mb-1 block text-xs font-medium text-text-secondary"
              >
                {scope === "team" ? "Team" : "Campus"}
              </label>
              <select
                id={`scope-${role.id}-${scope}`}
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
            <label
              htmlFor={`holder-${role.id}-${scope}`}
              className="mb-1 block text-xs font-medium text-text-secondary"
            >
              Person
            </label>
            <div className="flex flex-wrap gap-2">
              <select
                id={`holder-${role.id}-${scope}`}
                name="user"
                defaultValue=""
                className="min-w-44 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
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
                disabled={busy}
                className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Saving..." : "Save holder"}
              </button>
            </div>
          </div>
          {error && <p className="text-xs text-status-rejected">{error}</p>}
        </form>
      )}
    </div>
  );
}
