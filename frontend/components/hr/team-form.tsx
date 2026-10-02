"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";

import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import type {
  Campus,
  Team,
  TeamInput,
  TeamSectionInput,
  TeamWorkflowInput,
} from "@/lib/teams";
import { createTeam, updateTeam } from "@/lib/teams-client";

interface DraftSection {
  name: string;
  approver_role: string;
  members: number[];
}

/**
 * One form for a whole team: who it is, when it is in force, and the chain its
 * applications follow.
 *
 * There is no separate workflow screen. A chain exists because a team has one,
 * so it is described and kept here — created with the team, edited with it —
 * and a team can never be pointed at a chain that belongs to somebody else.
 *
 * There is deliberately no "active" checkbox either. Putting a team into force
 * and taking it out are validated, audited decisions with their own actions, so
 * a single edit cannot quietly put an unstaffed chain in front of an employee.
 */
export function TeamForm({
  team,
  campuses,
  roles,
  employees = [],
  rolesError = "",
  peopleError = "",
  onSuccess,
  onCancel,
}: {
  team?: Team;
  campuses: Campus[];
  roles: ApproverRole[];
  /** Only needed when creating: picking the people who start on each step. */
  employees?: Employee[];
  /** Set when the roles fetch failed; the chain builder needs its options. */
  rolesError?: string;
  peopleError?: string;
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
  const [sections, setSections] = useState<DraftSection[]>(() =>
    team
      ? team.sections.map((section) => ({
          name: section.name,
          approver_role: section.approver_role,
          // An existing step's roster is edited on the team page, one person at
          // a time, because that is an audited action of its own. The builder
          // edits the *steps*, not the people on them.
          members: [],
        }))
      : roles.length > 0
        ? [{ name: "", approver_role: roles[0].code, members: [] }]
        : []
  );

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

  function update(index: number, patch: Partial<DraftSection>) {
    setSections((current) =>
      current.map((section, i) => (i === index ? { ...section, ...patch } : section))
    );
  }

  function toggleMember(index: number, userId: number) {
    setSections((current) =>
      current.map((section, i) => {
        if (i !== index) return section;
        return section.members.includes(userId)
          ? { ...section, members: section.members.filter((id) => id !== userId) }
          : { ...section, members: [...section.members, userId] };
      })
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const campus = String(formData.get("campus") || "");
    const effectiveFrom = String(formData.get("effective_from") || "");
    const effectiveTo = String(formData.get("effective_to") || "");

    const input: TeamInput = {
      name: String(formData.get("name") || "").trim(),
      description: String(formData.get("description") || "").trim(),
      department: String(formData.get("department") || "").trim(),
      campus: campus ? Number(campus) : null,
      effective_from: effectiveFrom || null,
      effective_to: effectiveTo || null,
    };

    const named = sections.filter((section) => section.name.trim() !== "");
    if (named.length === 0) {
      setError(
        team
          ? "This team has no approval steps. Add at least one."
          : "Describe at least one approval step, or name the step you add."
      );
      setLoading(false);
      return;
    }
    if (named.some((section) => section.approver_role === "")) {
      setError("Every step needs a role, or the chain cannot be read.");
      setLoading(false);
      return;
    }
    if (!team && named.some((section) => section.members.length === 0)) {
      // Only on create. An empty step can be fixed later on the team page, but
      // a chain built here with nobody on it is a chain that does not route,
      // and the author is right there looking at it.
      setError("Give every step at least one person who can act, or the team cannot route.");
      setLoading(false);
      return;
    }

    const newWorkflow: TeamWorkflowInput = {
      name: String(formData.get("chain_name") || "").trim() || undefined,
      sections: named.map(
        (section): TeamSectionInput => ({
          name: section.name.trim(),
          approver_role: section.approver_role,
          ...(team ? {} : { members: section.members }),
        })
      ),
    };
    input.new_workflow = newWorkflow;

    try {
      const saved = team
        ? await updateTeam(team.id, input)
        : await createTeam(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push(
          team ? `/dashboard/hr-admin/teams/${team.id}` : "/dashboard/hr-admin/teams"
        );
        router.refresh();
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  const activeEmployees = employees.filter((employee) => employee.is_active);

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
          defaultValue={team?.name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Bunda College Faculty"
        />
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
          defaultValue={team?.campus ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">No campus</option>
          {campuses.map((campus) => (
            <option key={campus.id} value={campus.id}>
              {campus.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          Optional. Scopes the team for reporting and history.
        </p>
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
          defaultValue={team?.description}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Who belongs on this team"
        />
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
          defaultValue={team?.department}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Administration"
        />
        <p className="mt-1 text-xs text-text-muted">
          Optional. Two teams in force in the same department is a
          configuration problem the readiness check will report, not an error
          here — a reorganization can legitimately have a handover period.
        </p>
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
          defaultValue={team?.effective_from ?? ""}
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
          defaultValue={team?.effective_to ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Optional. A dated end is how a team is handed over without a gap.
        </p>
      </div>

      <fieldset className="md:col-span-2 space-y-3">
        <legend className="text-sm font-medium text-text-primary">
          Approval chain
        </legend>
        <p className="text-xs text-text-muted">
          The steps this team&apos;s applications follow, in order. A step is
          decided by whichever of its members acts first, so it is a roster with
          one seat taken per decision — not a single named approver.
        </p>

        {rolesError ? (
          <p
            role="alert"
            className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected"
          >
            {rolesError}
          </p>
        ) : null}

        <div>
          <label
            htmlFor="chain_name"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Chain name
          </label>
          <input
            id="chain_name"
            name="chain_name"
            defaultValue={team?.workflow_name ?? ""}
            placeholder={
              team ? "Leave blank to keep the current name" : "Leave blank to name it after the team"
            }
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">
            Approval steps
          </span>
          <button
            type="button"
            onClick={() =>
              setSections((current) => [
                ...current,
                {
                  name: "",
                  approver_role: roles[0]?.code ?? "",
                  members: [],
                },
              ])
            }
            disabled={rolesUnavailable}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            Add step
          </button>
        </div>

        {peopleError ? (
          <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {peopleError}
          </p>
        ) : null}

        {sections.map((section, index) => (
          <div
            key={index}
            role="group"
            aria-label={`Step ${index + 1}`}
            className="rounded-md border border-border-default bg-surface-card p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="grid size-8 shrink-0 place-content-center rounded-full bg-brand-primary-subtle text-sm font-semibold text-brand-primary">
                {index + 1}
              </span>
              <input
                aria-label={`Step ${index + 1} name`}
                value={section.name}
                onChange={(event) => update(index, { name: event.target.value })}
                placeholder="e.g. Supervisor approval"
                className="min-w-36 flex-1 rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              />
              <select
                aria-label={`Step ${index + 1} role`}
                value={section.approver_role}
                disabled={rolesUnavailable}
                onChange={(event) =>
                  update(index, { approver_role: event.target.value })
                }
                className="min-w-44 flex-1 rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-40"
              >
                {section.approver_role === "" && (
                  <option value="">Choose a role…</option>
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
                  aria-label={`Move step ${index + 1} up`}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label={`Move step ${index + 1} down`}
                  disabled={index === sections.length - 1}
                  onClick={() => move(index, 1)}
                  className="grid size-8 place-content-center rounded-md border border-border-default text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ArrowDown className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label={`Remove step ${index + 1}`}
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

            {!team && (
              <fieldset className="mt-2 pl-10">
                <legend className="text-xs font-medium text-text-secondary">
                  Who can act at this step
                </legend>
                {activeEmployees.length === 0 && !peopleError ? (
                  <p className="text-xs text-text-muted">
                    No active people to choose from.
                  </p>
                ) : (
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                    {activeEmployees.map((employee) => (
                      <label
                        key={employee.user_id}
                        className="flex items-center gap-1.5 text-sm text-text-secondary"
                      >
                        <input
                          type="checkbox"
                          checked={section.members.includes(employee.user_id)}
                          onChange={() => toggleMember(index, employee.user_id)}
                          className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
                        />
                        {employee.full_name || employee.email}
                      </label>
                    ))}
                  </div>
                )}
                <p className="mt-1 text-xs text-text-muted">
                  Everybody in force can be added or taken off later from the
                  team&apos;s own page, one person at a time.
                </p>
              </fieldset>
            )}
          </div>
        ))}
      </fieldset>

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
          disabled={loading || sections.length === 0}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : team ? "Save changes" : "Create team"}
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
            href={team ? `/dashboard/hr-admin/teams/${team.id}` : "/dashboard/hr-admin/teams"}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
