"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowLeft, ArrowUp, Plus, X } from "lucide-react";

import { createApproverRole } from "@/lib/approver-roles-client";
import type { ApproverRole } from "@/lib/approver-roles";
import { createDepartment } from "@/lib/departments-client";
import type { Department } from "@/lib/departments";
import type {
  Campus,
  EligibleApprover,
  Team,
  TeamInput,
  TeamSectionInput,
  TeamWorkflowInput,
} from "@/lib/teams";
import { createTeam, listEligibleApprovers, updateTeam } from "@/lib/teams-client";

interface DraftSection {
  name: string;
  approver_role: string;
  approver: number | null;
}

/**
 * Two pages, because the two questions are not one question.
 *
 * Page one is what the team *is*: its name, the department it belongs to, and
 * its window. Page two is who decides for it, one named person per step. The
 * department comes first because it decides who may be appointed at all — an
 * approver is one of the team's own employees — so picking people before naming
 * the department would mean offering the whole staff and refusing half of them
 * on save.
 *
 * A team with no steps can still be saved. It becomes a draft, routes nothing,
 * and the chain is added from its own page when HR is ready. That is why "Save
 * as draft" sits beside "Create team" rather than behind an extra screen.
 */
export function TeamForm({
  team,
  campuses,
  departments: initialDepartments,
  roles: initialRoles,
  departmentsError = "",
  rolesError = "",
}: {
  team?: Team;
  campuses: Campus[];
  departments: Department[];
  roles: ApproverRole[];
  /** Set when the departments fetch failed; the picker needs its options. */
  departmentsError?: string;
  /** Set when the roles fetch failed; the chain builder needs its options. */
  rolesError?: string;
}) {
  const router = useRouter();
  // The server-loaded options are the starting point, not the final word: HR
  // can create a department or a role from this form, and the option they just
  // made must appear in the picker without leaving the page.
  const [departments, setDepartments] = useState<Department[]>(initialDepartments);
  const [roles, setRoles] = useState<ApproverRole[]>(initialRoles);
  const [showNewDepartment, setShowNewDepartment] = useState(false);
  const [newDepartmentName, setNewDepartmentName] = useState("");
  const [departmentCreateError, setDepartmentCreateError] = useState("");
  const [creatingDepartment, setCreatingDepartment] = useState(false);
  const [showNewRole, setShowNewRole] = useState(false);
  const [newRoleLabel, setNewRoleLabel] = useState("");
  const [roleCreateError, setRoleCreateError] = useState("");
  const [creatingRole, setCreatingRole] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState<1 | 2>(team ? 2 : 1);
  const [department, setDepartment] = useState<string>(
    team?.department === null || team?.department === undefined
      ? ""
      : String(team.department)
  );
  // The details form is unmounted while page two is shown, so its values have to
  // outlive it. Read once when the second page mounts; page two only ever reads
  // them, so nothing can go stale behind the user's back.
  const [details, setDetails] = useState<TeamDetails>({
    name: team?.name ?? "",
    description: team?.description ?? "",
    campus: team?.campus ?? null,
    effective_from: team?.effective_from ?? "",
    effective_to: team?.effective_to ?? "",
  });
  const [chainName, setChainName] = useState(team?.workflow_name ?? "");
  const [sections, setSections] = useState<DraftSection[]>(() =>
    team
      ? team.sections.map((section) => ({
          name: section.name,
          approver_role: section.approver_role,
          approver: section.approver?.id ?? null,
        }))
      : []
  );

  const departmentsUnavailable = departmentsError !== "" || departments.length === 0;
  const rolesUnavailable = rolesError !== "" || roles.length === 0;

  /** Roles carry an id the eligibility endpoint filters on; sections carry a code. */
  const roleIdByCode = useMemo(() => {
    const ids = new Map<string, number>();
    roles.forEach((role) => ids.set(role.code, role.id));
    return ids;
  }, [roles]);

  /** The full role, so a step can tell whether it is institution-wide. */
  const roleByCode = useMemo(() => {
    const byCode = new Map<string, ApproverRole>();
    roles.forEach((role) => byCode.set(role.code, role));
    return byCode;
  }, [roles]);

  /**
   * One picker per step, and each one asks the backend who may act at *that*
   * step. Fetching per step rather than once for the team is deliberate: the
   * eligible people differ per role, and a shared list would either offer
   * somebody who cannot hold this step or hide somebody who can.
   */
  const [candidates, setCandidates] = useState<Record<string, EligibleApprover[]>>(
    {}
  );
  const [candidateError, setCandidateError] = useState("");

  // The departments and roles a fetch is needed for, as a stable string so that
  // typing a step's name does not re-ask the same question on every keystroke.
  const candidateKeys = useMemo(() => {
    const departmentId = department ? Number(department) : null;
    if (departmentId === null) return "";
    const roleIds = new Set<number>();
    sections.forEach((section) => {
      const roleId = roleIdByCode.get(section.approver_role);
      if (roleId !== undefined) roleIds.add(roleId);
    });
    return [...roleIds].map((roleId) => `${departmentId}:${roleId}`).join(",");
  }, [department, sections, roleIdByCode]);

  useEffect(() => {
    if (candidateKeys === "") {
      return;
    }
    let cancelled = false;
    Promise.all(
      candidateKeys.split(",").map(async (key) => {
        const [departmentPart, rolePart] = key.split(":");
        const people = await listEligibleApprovers(
          Number(departmentPart),
          Number(rolePart)
        );
        return [key, people] as const;
      })
    )
      .then((entries) => {
        if (cancelled) return;
        const loaded = Object.fromEntries(entries);
        setCandidates(loaded);
        setCandidateError("");

        /**
         * Selecting an institution-wide role is the appointment.
         *
         * A role that approves across the whole institution is held outside the
         * department, so its holder cannot be found by browsing this team's
         * employees. When the fetched candidates leave exactly one holder, the
         * step is filled in as soon as they are known — the same holder the
         * backend appoints on save — so the reviewer sees who decides instead of
         * a step that looks empty. Several holders stay a real choice and are left
         * to HR.
         *
         * Applied here rather than in an effect of its own: the appointment is
         * only possible once the candidates arrive, which is the same moment the
         * picker gains the option.
         */
        const departmentId = department ? Number(department) : null;
        if (departmentId === null) return;
        setSections((current) => {
          let changed = false;
          const next = current.map((section) => {
            if (section.approver !== null) return section;
            const role = roleByCode.get(section.approver_role);
            if (!role?.is_institution_wide) return section;
            const roleId = roleIdByCode.get(section.approver_role);
            if (roleId === undefined) return section;
            const options = loaded[`${departmentId}:${roleId}`] ?? [];
            if (options.length !== 1) return section;
            changed = true;
            return { ...section, approver: options[0].id };
          });
          return changed ? next : current;
        });
      })
      .catch(() => {
        if (cancelled) return;
        setCandidateError(
          "Unable to load the people who may approve in this department."
        );
      });
    return () => {
      cancelled = true;
    };
  }, [candidateKeys, department, roleByCode, roleIdByCode]);

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

  /**
   * Re-reads the people for one step when its role changes, because the person
   * chosen for the previous role is very likely not eligible for the new one.
   * Clearing rather than keeping it: sending an ineligible id would only earn a
   * refusal on save.
   */
  function changeRole(index: number, approverRole: string) {
    update(index, { approver_role: approverRole, approver: null });
  }

  /**
   * Create a department without leaving the team being built.
   *
   * The department is the pivot the rest of the form depends on: it decides who
   * may be appointed at each step. Sending HR to another page and back would
   * throw away the chain they had started describing, so the creation is done
   * here and the new department is selected immediately.
   */
  async function handleCreateDepartment() {
    const name = newDepartmentName.trim();
    if (name === "") return;
    setDepartmentCreateError("");
    setCreatingDepartment(true);
    try {
      const created = await createDepartment({ name });
      setDepartments((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      setDepartment(String(created.id));
      setNewDepartmentName("");
      setShowNewDepartment(false);
    } catch (err) {
      setDepartmentCreateError(
        err instanceof Error ? err.message : "Could not create the department."
      );
    } finally {
      setCreatingDepartment(false);
    }
  }

  /**
   * Create an approver role while describing a stage.
   *
   * A stage needs a role, and a role is just a name. Requiring HR to abandon a
   * half-written chain to go and make one would be the missing-UI problem the
   * seed used to paper over; making it here keeps the configuration in one
   * place.
   */
  async function handleCreateRole() {
    const label = newRoleLabel.trim();
    if (label === "") return;
    setRoleCreateError("");
    setCreatingRole(true);
    try {
      const created = await createApproverRole({ label });
      setRoles((current) => [...current, created]);
      setNewRoleLabel("");
      setShowNewRole(false);
    } catch (err) {
      setRoleCreateError(
        err instanceof Error ? err.message : "Could not create the role."
      );
    } finally {
      setCreatingRole(false);
    }
  }

  function describeSteps(): TeamSectionInput[] {
    return sections
      .filter((section) => section.name.trim() !== "")
      .map((section) => ({
        name: section.name.trim(),
        approver_role: section.approver_role,
        ...(section.approver === null ? {} : { approver: section.approver }),
      }));
  }

interface TeamDetails {
  name: string;
  description: string;
  campus: number | null;
  effective_from: string;
  effective_to: string;
}

  async function save(draft: boolean, chainName = "") {
    setError("");
    setLoading(true);

    const input: TeamInput = {
      name: details.name.trim(),
      description: details.description.trim(),
      department: department ? Number(department) : null,
      campus: details.campus,
      effective_from: details.effective_from || null,
      effective_to: details.effective_to || null,
    };

    const named = describeSteps();

    if (!draft) {
      if (named.length === 0) {
        setError(
          team
            ? "This team has no approval steps. Add at least one."
            : "Describe at least one approval step, or save the team as a draft."
        );
        setLoading(false);
        return;
      }
      if (named.some((section) => section.approver_role === "")) {
        setError("Every step needs a role, or the chain cannot be read.");
        setLoading(false);
        return;
      }
      // An institution-wide step needs no pick: selecting its role appoints the
      // holder, and the backend writes them on save. Only a department-scoped
      // step with nobody named blocks submission.
      const unstaffed = sections.filter(
        (section) =>
          section.name.trim() !== "" &&
          section.approver === null &&
          roleByCode.get(section.approver_role)?.is_institution_wide !== true
      );
      if (unstaffed.length > 0) {
        setError(
          "Name the one person who decides at every step, or save the team as a draft."
        );
        setLoading(false);
        return;
      }
      const newWorkflow: TeamWorkflowInput = {
        name: chainName.trim() || undefined,
        sections: named,
      };
      input.new_workflow = newWorkflow;
    }

    try {
      if (team) {
        await updateTeam(team.id, input);
      } else {
        await createTeam(input);
      }
      router.push(team ? `/dashboard/hr-admin/teams/${team.id}` : "/dashboard/hr-admin/teams");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  /**
   * Page one hands over to page two without saving: a team is only written once
   * its chain is described (or once HR says draft), so a half-typed chain never
   * reaches the backend. The name is required by the browser, so the form's own
   * validation is the check.
   */
  async function handleDetailsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPage(2);
  }

  const backHref = team
    ? `/dashboard/hr-admin/teams/${team.id}`
    : "/dashboard/hr-admin/teams";

  if (page === 1) {
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
          <label
            htmlFor="campus"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Campus
          </label>
          <select
            id="campus"
            name="campus"
            value={details.campus === null ? "" : String(details.campus)}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                campus: event.target.value ? Number(event.target.value) : null,
              }))
            }
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

        <div className="md:col-span-2">
          <label
            htmlFor="department"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Department
          </label>
          <select
            id="department"
            name="department"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
            disabled={departmentsUnavailable}
            className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">No department</option>
            {departments.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-text-muted">
            {departmentsError ||
              "Decides who may be appointed as this team's approvers: only employees of this department. Two teams in force in the same department is a configuration problem the readiness check reports, not an error here."}
          </p>

          {!showNewDepartment ? (
            <button
              type="button"
              onClick={() => setShowNewDepartment(true)}
              className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              <Plus className="h-4 w-4" />
              Create department
            </button>
          ) : (
            <div className="mt-2 rounded-md border border-border-default bg-surface-muted p-3">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  aria-label="New department name"
                  value={newDepartmentName}
                  onChange={(event) => setNewDepartmentName(event.target.value)}
                  placeholder="e.g. ICT"
                  className="min-w-40 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
                />
                <button
                  type="button"
                  onClick={() => void handleCreateDepartment()}
                  disabled={creatingDepartment || newDepartmentName.trim() === ""}
                  className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {creatingDepartment ? "Saving..." : "Save department"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowNewDepartment(false);
                    setDepartmentCreateError("");
                  }}
                  className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
                >
                  Cancel
                </button>
              </div>
              {departmentCreateError ? (
                <p className="mt-1 text-xs text-status-rejected">
                  {departmentCreateError}
                </p>
              ) : null}
            </div>
          )}
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
            {loading ? "Saving..." : "Continue to approval steps"}
          </button>
          <Link
            href={backHref}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        </div>
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
          {department
            ? ` — ${departments.find((item) => String(item.id) === department)?.name ?? "department"}`
            : ""}
        </p>
        <h3 className="mt-1 text-sm font-semibold text-text-primary">
          Who approves for this team
        </h3>
        <p className="mt-1 text-xs text-text-muted">
          The steps this team&apos;s applications follow, in order. Each step has
          exactly one person: an application is routed to a named approver, not
          to whichever of several people happens to act first.
          {department
            ? ` Candidates are the employees of ${
                departments.find((item) => String(item.id) === department)?.name ??
                "this department"
              }.`
            : " Choose a department on the previous page to see who can approve."}
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

      <div className="md:col-span-2">
        <label
          htmlFor="chain_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Chain name
        </label>
        <input
          id="chain_name"
          name="chain_name"
          value={chainName}
          onChange={(event) => setChainName(event.target.value)}
          placeholder={
            team ? "Leave blank to keep the current name" : "Leave blank to name it after the team"
          }
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 md:col-span-2">
        <span className="text-sm font-medium text-text-primary">Approval steps</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowNewRole((current) => !current)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            <Plus className="h-4 w-4" />
            New role
          </button>
          <button
            type="button"
            onClick={() =>
              setSections((current) => [
                ...current,
                { name: "", approver_role: roles[0]?.code ?? "", approver: null },
              ])
            }
            disabled={rolesUnavailable}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            Add step
          </button>
        </div>
      </div>

      {showNewRole ? (
        <div className="rounded-md border border-border-default bg-surface-muted p-3 md:col-span-2">
          <div className="flex flex-wrap items-center gap-2">
            <input
              aria-label="New role name"
              value={newRoleLabel}
              onChange={(event) => setNewRoleLabel(event.target.value)}
              placeholder="e.g. Head of Department"
              className="min-w-40 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            />
            <button
              type="button"
              onClick={() => void handleCreateRole()}
              disabled={creatingRole || newRoleLabel.trim() === ""}
              className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creatingRole ? "Saving..." : "Save role"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNewRole(false);
                setRoleCreateError("");
              }}
              className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Cancel
            </button>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            The new role appears in every step&apos;s role picker. Behaviour such
            as history scope and cancellation handling is set on the Roles page.
          </p>
          {roleCreateError ? (
            <p className="mt-1 text-xs text-status-rejected">{roleCreateError}</p>
          ) : null}
        </div>
      ) : null}

      {candidateError ? (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2">
          {candidateError}
        </p>
      ) : null}

      {sections.length === 0 ? (
        <p className="text-sm text-text-muted md:col-span-2">
          No approval steps yet. A team with no steps is a draft and routes
          nothing, which is a legitimate way to save it and finish later.
        </p>
      ) : null}

      {sections.map((section, index) => {
        const roleId = roleIdByCode.get(section.approver_role);
        const isInstitutionWide =
          roleByCode.get(section.approver_role)?.is_institution_wide === true;
        const options = department && roleId
          ? candidates[`${department}:${roleId}`] ?? []
          : [];
        return (
          <div
            key={index}
            role="group"
            aria-label={`Step ${index + 1}`}
            className="rounded-md border border-border-default bg-surface-card p-3 md:col-span-2"
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
                onChange={(event) => changeRole(index, event.target.value)}
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

            <div className="mt-2 pl-10">
              <label
                htmlFor={`approver-${index}`}
                className="mb-1 block text-xs font-medium text-text-secondary"
              >
                Approver
              </label>
              <select
                id={`approver-${index}`}
                aria-label={`Step ${index + 1} approver`}
                value={section.approver === null ? "" : String(section.approver)}
                onChange={(event) =>
                  update(index, {
                    approver: event.target.value ? Number(event.target.value) : null,
                  })
                }
                disabled={!department || options.length === 0}
                className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">Choose an approver…</option>
                {options.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.full_name}
                    {person.designation ? ` — ${person.designation}` : ""}
                  </option>
                ))}
              </select>
              {!department ? (
                <p className="mt-1 text-xs text-text-muted">
                  Choose a department first — approvers are chosen from its
                  employees.
                </p>
              ) : isInstitutionWide ? (
                <p className="mt-1 text-xs text-text-muted">
                  Institution-wide role.{" "}
                  {options.length === 1
                    ? "Its holder approves automatically, wherever they sit."
                    : options.length === 0
                      ? "No active holder yet — appoint one on the Roles page."
                      : "Choose which holder decides at this step."}
                </p>
              ) : options.length === 0 ? (
                <p className="mt-1 text-xs text-text-muted">
                  Nobody in this department can hold this role yet. Appoint a
                  holder on the Roles page, or pick a different role.
                </p>
              ) : null}
            </div>
          </div>
        );
      })}

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
          onClick={() => void save(false, chainName)}
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : team ? "Save changes" : "Create team"}
        </button>
        <button
          type="button"
          onClick={() => void save(true, chainName)}
          disabled={loading}
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          Save as draft
        </button>
        <button
          type="button"
          onClick={() => setPage(1)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to details
        </button>
        <Link
          href={backHref}
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </div>
  );
}