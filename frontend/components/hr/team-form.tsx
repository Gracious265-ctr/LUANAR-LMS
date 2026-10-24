"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import type { ApproverRole } from "@/lib/approver-roles";
import type { TeamCategory } from "@/lib/team-category";
import { TEAM_CATEGORY_LABELS } from "@/lib/team-category";
import type { Employee } from "@/lib/employees";
import type { Campus, Team, TeamInput } from "@/lib/teams";
import { createTeam, updateTeam } from "@/lib/teams-client";

/**
 * Creating a team is two questions, in order.
 *
 * First what the team *is* — its kind, academic or administration, its campus
 * when it is academic, its name, and its window. Then who runs it: a manager,
 * named as a team-scoped approver role and the person who holds it. The manager
 * is the only person who configures the team's members, its chains, and which
 * chain routes, so HR's job ends at naming them; there is no chain builder here
 * for HR to visit, and the manager step is a required half of creation rather
 * than an optional extra.
 *
 * Editing keeps the details only. The manager is changed from the team's
 * Approvers tab, where the wide-holder panel already offers "Make manager", and
 * the chain is the manager's own screen.
 *
 * A team with no steps can still be saved: it is created active and routes
 * nothing until its manager builds and routes a chain.
 */
export function TeamForm({
  team,
  campuses,
  roles = [],
  rolesError = "",
  employees = [],
  wideHolderUserIds = [],
  onSuccess,
  onCancel,
}: {
  team?: Team;
  campuses: Campus[];
  /**
   * The team-scoped roles a manager may hold: active roles that are not
   * institution-wide. Filtered by the page so the picker cannot offer a role
   * the backend would refuse at team scope.
   */
  roles?: ApproverRole[];
  /** Set when the roles fetch failed; the manager picker needs its options. */
  rolesError?: string;
  /**
   * Everyone the manager picker may offer. Scoped to the team's category in the
   * picker rather than here, because on create the category is chosen on the
   * first page and is not known until the second one renders.
   */
  employees?: Employee[];
  /**
   * Every current wide approver, whatever their scope. A person holds only one
   * wide approver role, so somebody who already holds one is left out of the
   * manager picker — the same rule the wide-holder panel enforces.
   */
  wideHolderUserIds?: number[];
  /**
   * Called with the saved team instead of navigating, so a host overlay can
   * close and refresh in place. Omit it and the form navigates itself, which is
   * what the standalone edit page still relies on.
   */
  onSuccess?: (team: Team) => void;
  /** Replaces the cancel link when the host already knows where to go back to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState<1 | 2>(1);
  const [managerRoleId, setManagerRoleId] = useState("");
  const [managerUserId, setManagerUserId] = useState("");
  // The details form is unmounted while page two is shown, so its values have to
  // outlive it. Page two only ever reads them, so nothing can go stale.
  const [details, setDetails] = useState<TeamDetails>({
    name: team?.name ?? "",
    description: team?.description ?? "",
    category: (team?.category as TeamCategory) ?? "administration",
    campus: team?.campus ?? null,
    effective_from: team?.effective_from ?? "",
    effective_to: team?.effective_to ?? "",
  });

  const rolesUnavailable = rolesError !== "" || roles.length === 0;
  const excludedWideHolders = useMemo(
    () => new Set(wideHolderUserIds),
    [wideHolderUserIds]
  );

  /**
   * The people who may manage this team.
   *
   * A manager is a team-wide approver, so the same rules the write enforces are
   * applied here: they must be an active employee of the team's own category,
   * and they cannot already hold a wide approver role anywhere — a person holds
   * only one, so offering them would be a save that can only fail.
   */
  const managerCandidates = useMemo(
    () =>
      employees.filter(
        (employee) =>
          employee.is_active &&
          employee.category === details.category &&
          !excludedWideHolders.has(employee.user_id)
      ),
    [employees, details.category, excludedWideHolders]
  );

  /**
   * Where page one goes.
   *
   * An edit saves the details and stops — there is no manager step and no chain
   * builder. A create advances to the manager step, but only once the academic
   * campus rule is satisfied, so the second page cannot be reached with a team
   * the save would refuse.
   */
  async function handleDetailsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (details.category === "academic" && details.campus === null) {
      setError(
        "An academic team sits at a campus. Choose one, or create it first — the campus is what makes campus-wide approvers reachable for this team's stages."
      );
      return;
    }
    if (team) {
      await save();
      return;
    }
    setPage(2);
  }

  async function save() {
    setError("");
    setLoading(true);

    const input: TeamInput = {
      name: details.name.trim(),
      description: details.description.trim(),
      category: details.category,
      // An administration team has no campus, so the field is not merely left
      // empty — it is cleared — and an academic team cannot be saved without
      // one. The rule is stated here in the same words the backend refuses in,
      // so the form names the fix rather than showing a server error.
      campus: details.category === "academic" ? details.campus : null,
      effective_from: details.effective_from || null,
      effective_to: details.effective_to || null,
    };

    if (details.category === "academic" && input.campus === null) {
      setError(
        "An academic team sits at a campus. Choose one, or create it first — the campus is what makes campus-wide approvers reachable for this team's stages."
      );
      setLoading(false);
      setPage(1);
      return;
    }

    if (!team) {
      const role = Number(managerRoleId) || 0;
      const user = Number(managerUserId) || 0;
      if (!role) {
        setError(
          "Choose the team-scoped role the manager will hold, so the backend knows what they may decide."
        );
        setLoading(false);
        return;
      }
      if (!user) {
        setError(
          "Choose who will manage this team. Only an active employee of this team's category who holds no wide approver role is offered."
        );
        setLoading(false);
        return;
      }
      input.manager = { role, user };
    }

    try {
      const saved = team
        ? await updateTeam(team.id, input)
        : await createTeam(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        // A new team is now the manager's to run: HR's part is describing the
        // team and naming who runs it, and the team's own page is where the
        // manager takes over.
        router.push(
          team ? `/dashboard/teams/${team.id}` : `/dashboard/teams/${saved.id}`
        );
        router.refresh();
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
      if (!team) {
        setPage(2);
      }
    } finally {
      setLoading(false);
    }
  }

  const backHref = team
    ? `/dashboard/teams/${team.id}`
    : "/dashboard/teams";

  if (page === 1 || team) {
    return (
      <form
        id="team-details"
        onSubmit={handleDetailsSubmit}
        className="grid grid-cols-1 gap-4 md:grid-cols-2"
      >
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
            value={details.name}
            onChange={(event) =>
              setDetails((current) => ({ ...current, name: event.target.value }))
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            placeholder="e.g. Bunda College Faculty"
          />
        </div>

        <div>
          <span
            id="category-label"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Category
          </span>
          <div
            role="radiogroup"
            aria-labelledby="category-label"
            className="flex flex-wrap gap-2"
          >
            {(
              [
                {
                  value: "administration",
                  hint: "Institution-wide. The only kind an institution-wide approver may serve.",
                },
                {
                  value: "academic",
                  hint: "Sits at a campus, and may use campus-wide approvers.",
                },
              ] as const
            ).map((option) => {
              const selected = details.category === option.value;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                    selected
                      ? "border-brand-primary bg-brand-primary-subtle text-text-primary"
                      : "border-border-default bg-surface-page text-text-secondary hover:bg-button-secondary-hover"
                  }`}
                >
                  <input
                    type="radio"
                    name="category"
                    value={option.value}
                    checked={selected}
                    onChange={() =>
                      setDetails((current) => ({
                        ...current,
                        category: option.value,
                        // Choosing a category that has no campus empties the
                        // field rather than leaving a value the backend will
                        // refuse — the two always agree on this form.
                        campus:
                          option.value === "academic" ? current.campus : null,
                      }))
                    }
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium">
                      {TEAM_CATEGORY_LABELS[option.value]}
                    </span>
                    <span className="mt-0.5 block text-xs text-text-muted">
                      {option.hint}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div>
          <label
            htmlFor="campus"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Campus
          </label>
          <select
            id="campus"
            name="campus"
            disabled={details.category !== "academic"}
            value={details.campus === null ? "" : String(details.campus)}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                campus: event.target.value ? Number(event.target.value) : null,
              }))
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">
              {details.category === "academic"
                ? "Choose a campus…"
                : "Not campus-based"}
            </option>
            {campuses.map((campus) => (
              <option key={campus.id} value={campus.id}>
                {campus.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-text-muted">
            {details.category === "academic"
              ? "Required. Scopes campus-wide approvers to this team's stages."
              : "An administration team is institution-wide and does not sit at a campus."}
          </p>
          {details.category === "academic" && campuses.length === 0 && (
            <p className="mt-1 text-xs text-status-pending">
              No campuses yet. Create one first —{" "}
              <Link
                href="/dashboard/hr-admin/campuses/new"
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                New campus
              </Link>
              .
            </p>
          )}
        </div>

        <div className="md:col-span-2">
          <label
            htmlFor="description"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Description
          </label>
          <input
            id="description"
            name="description"
            value={details.description}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            placeholder="Who belongs on this team"
          />
        </div>

        <div>
          <label
            htmlFor="effective_from"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            In force from
          </label>
          <input
            id="effective_from"
            name="effective_from"
            type="date"
            value={details.effective_from}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                effective_from: event.target.value,
              }))
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
          <p className="mt-1 text-xs text-text-muted">
            Blank means from the day the team is activated.
          </p>
        </div>

        <div>
          <label
            htmlFor="effective_to"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            In force until
          </label>
          <input
            id="effective_to"
            name="effective_to"
            type="date"
            value={details.effective_to}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                effective_to: event.target.value,
              }))
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
          <p className="mt-1 text-xs text-text-muted">
            Optional. A dated end is how a team is handed over without a gap.
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2"
          >
            {error}
          </div>
        )}

        <div className="flex items-center gap-3 md:col-span-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Saving..." : team ? "Save changes" : "Next"}
          </button>
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
              href={backHref}
              className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Cancel
            </Link>
          )}
        </div>
        {!team ? (
          <p className="text-xs text-text-muted md:col-span-2">
            Next, assign the team&apos;s manager. The manager alone configures
            the team&apos;s members, approval chains, and which chain routes.
          </p>
        ) : null}
      </form>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <p className="text-xs text-text-muted">
          <span className="font-medium text-text-secondary">
            {details.name || "This team"}
          </span>
          {details.campus === null
            ? ""
            : " — " +
              (campuses.find((campus) => campus.id === details.campus)?.name ??
                "campus")}
        </p>
        <h3 className="mt-1 text-sm font-semibold text-text-primary">
          Assign team manager
        </h3>
        <p className="mt-1 text-xs text-text-muted">
          The manager is a team-wide approver who runs this team: they add its
          members, build its approval chains, staff each step, and decide which
          chain routes. They hold one of the team-scoped roles, and must be an
          active employee of the team&apos;s own category. A person may hold only
          one wide approver role, so anyone who already holds one anywhere is not
          offered here.
        </p>
      </div>

      {rolesError ? (
        <p
          role="alert"
          className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2"
        >
          {rolesError}
        </p>
      ) : null}

      <div>
        <label
          htmlFor="manager-role"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Manager role
        </label>
        <select
          id="manager-role"
          name="manager_role"
          value={managerRoleId}
          disabled={rolesUnavailable}
          onChange={(event) => setManagerRoleId(event.target.value)}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Choose a team-scoped role…</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          {rolesUnavailable
            ? "No team-scoped roles are available. Create one on the Roles page first."
            : "Only active, team-scoped roles are offered — an institution-wide role is held outside a single team."}
        </p>
      </div>

      <div>
        <label
          htmlFor="manager-user"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Manager
        </label>
        <select
          id="manager-user"
          name="manager_user"
          value={managerUserId}
          disabled={managerCandidates.length === 0}
          onChange={(event) => setManagerUserId(event.target.value)}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Choose a person…</option>
          {managerCandidates.map((employee) => (
            <option key={employee.user_id} value={employee.user_id}>
              {employee.full_name || employee.email}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          {managerCandidates.length === 0
            ? "Nobody matching this team's category is free to manage it. Everyone who does already holds a wide approver role, or is not an active employee of this category."
            : `Only active ${TEAM_CATEGORY_LABELS[details.category].toLowerCase()} employees who hold no wide approver role are offered.`}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2"
        >
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : "Save team"}
        </button>
        <button
          type="button"
          onClick={() => setPage(1)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
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
            href={backHref}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        )}
      </div>
    </div>
  );
}

interface TeamDetails {
  name: string;
  description: string;
  /**
   * Academic or administration, and the campus is the visible half of the
   * rule: an academic team sits at a campus, an administration team is
   * institution-wide and does not.
   */
  category: TeamCategory;
  campus: number | null;
  effective_from: string;
  effective_to: string;
}
