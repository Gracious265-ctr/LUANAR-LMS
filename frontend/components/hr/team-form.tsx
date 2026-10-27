"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowLeft, ArrowUp, Plus, X } from "lucide-react";

import { createApproverRole } from "@/lib/approver-roles-client";
import type { ApproverRole } from "@/lib/approver-roles";
import type { TeamCategory } from "@/lib/team-category";
import { TEAM_CATEGORY_LABELS } from "@/lib/team-category";
import type { Employee } from "@/lib/employees";
import type {
  Campus,
  EligibleApprover,
  Team,
  TeamInput,
  TeamSectionInput,
} from "@/lib/teams";
import { createTeam, listEligibleApprovers, updateTeam } from "@/lib/teams-client";
import { buttonVariants, Button } from "@/components/ui/button";
import { FormProgress, type FormProgressStage } from "@/components/ui/form-progress";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/states";

interface DraftSection {
  /**
   * The role this step needs, by code. The step's name is derived from the
   * role's label on save, so there is nothing typed here beyond the two picks.
   */
  approver_role: string;
  approver: number | null;
}

/**
 * Two pages for every team, but not the same two.
 *
 * Creating a team asks what the team *is* — its kind, academic or
 * administration, its campus when it is academic, its name, and its window —
 * and then who runs it: one person, chosen by name. The manager need not hold a
 * team-scoped role, because the designation is the team's own `manager` field;
 * an institution-wide approver is a valid choice. The team is written as a
 * chainless draft, and the manager is the only one who configures its members,
 * its chains, and which chain routes, so HR's part ends at naming them; the next
 * screen is the new team's Members tab, where its roster is built.
 *
 * Editing keeps the two-page shape. Page one is the same details; page two is
 * who decides for the team, one named person per step. Eligibility is answered
 * by the team itself, so the picker is scoped by `?team=` and offers only
 * people already on the team. The manager is not set here — a team's manager is
 * changed from its Approvers tab, where the wide-holder panel offers "Make
 * manager".
 *
 * A team with no steps can still be saved. It becomes a draft, routes nothing,
 * and the chain is added from its own page when HR is ready. That is why on an
 * edit "Save as draft" sits beside "Save changes" rather than behind an extra
 * screen.
 */
export function TeamForm({
  team,
  campuses,
  roles: initialRoles,
  rolesError = "",
  employees = [],
  onSuccess,
  onCancel,
}: {
  team?: Team;
  campuses: Campus[];
  roles: ApproverRole[];
  /** Set when the roles fetch failed; the chain builder needs its options. */
  rolesError?: string;
  /**
   * Everyone the create form's manager picker may offer: the manager is named
   * when the team is created, so the people who may run it have to be known
   * before the save. Any active employee is eligible — the manager is not
   * required to hold a team-scoped role, and may be an institution-wide
   * approver.
   */
  employees?: Employee[];
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
  // The server-loaded roles are the starting point, not the final word: HR can
  // create a role from this form, and the one they just made must appear in
  // the picker without leaving the page.
  const [roles, setRoles] = useState<ApproverRole[]>(initialRoles);
  const [showNewRole, setShowNewRole] = useState(false);
  const [newRoleLabel, setNewRoleLabel] = useState("");
  const [roleCreateError, setRoleCreateError] = useState("");
  const [creatingRole, setCreatingRole] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState<1 | 2>(team ? 2 : 1);
  // The details form is unmounted while page two is shown, so its values have to
  // outlive it. Read once when the second page mounts; page two only ever reads
  // them, so nothing can go stale behind the user's back.
  const [details, setDetails] = useState<TeamDetails>({
    name: team?.name ?? "",
    description: team?.description ?? "",
    category: (team?.category as TeamCategory) ?? "administration",
    campus: team?.campus ?? null,
    effective_from: team?.effective_from ?? "",
    effective_to: team?.effective_to ?? "",
  });
  const [sections, setSections] = useState<DraftSection[]>(() =>
    team
      ? team.sections.map((section) => ({
          approver_role: section.approver_role,
          approver: section.approver?.id ?? null,
        }))
      : []
  );
  // The manager is named on the create form's second page. It is a create-only
  // decision: an existing team's manager is changed from its Approvers tab.
  const [managerUserId, setManagerUserId] = useState("");

  /**
   * The pages, in order, as the progress rail names them. Creating ends on the
   * manager who runs the new team; editing ends on the chain it already owns.
   */
  const stages: FormProgressStage[] = team
    ? [
        { id: "details", label: "Team details" },
        { id: "steps", label: "Approval steps" },
      ]
    : [
        { id: "details", label: "Team details" },
        { id: "manager", label: "Team manager" },
      ];

  const rolesUnavailable = rolesError !== "" || roles.length === 0;

  /**
   * The people who may run this team.
   *
   * Every active employee with a record, in either half of the institution: the
   * manager is designated on the team itself, so an institution-wide approver —
   * who holds no team-scoped role — is a valid choice. Being a wide holder is
   * not a bar either: running a team is a post, not a second wide holding.
   */
  const managerCandidates = useMemo(
    () =>
      [...employees]
        .filter((employee) => employee.is_active)
        .sort((left, right) => left.full_name.localeCompare(right.full_name)),
    [employees]
  );

  /**
   * Eligibility is answered by the team, so a team that does not exist yet has
   * nobody to offer: the picker stays closed until there is a team id to scope
   * it by.
   */
  const teamId = team?.id ?? null;

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
   * A step's name is its role's label.
   *
   * HR picks the role and nothing else, so the label is what the step is called:
   * the chain then reads the way the Roles page does, and two people configuring
   * the same team cannot end up with "Supervisor review" and "Supervisor
   * approval" sitting on the same step.
   */
  const roleLabelByCode = useMemo(() => {
    const labels = new Map<string, string>();
    roles.forEach((role) => labels.set(role.code, role.label));
    return labels;
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

  // The team and roles a fetch is needed for, as a stable string so that adding,
  // reordering or re-picking a step's role does not re-ask the same question on
  // every change.
  const candidateKeys = useMemo(() => {
    if (teamId === null) return "";
    const roleIds = new Set<number>();
    sections.forEach((section) => {
      const roleId = roleIdByCode.get(section.approver_role);
      if (roleId !== undefined) roleIds.add(roleId);
    });
    return [...roleIds].map((roleId) => `${teamId}:${roleId}`).join(",");
  }, [teamId, sections, roleIdByCode]);

  useEffect(() => {
    if (candidateKeys === "") {
      return;
    }
    let cancelled = false;
    Promise.all(
      candidateKeys.split(",").map(async (key) => {
        const [teamPart, rolePart] = key.split(":");
        const people = await listEligibleApprovers(
          Number(teamPart),
          Number(rolePart)
        );
        return [key, people] as const;
      })
    )
      .then((entries) => {
        if (cancelled) return;
        setCandidates(Object.fromEntries(entries));
        setCandidateError("");
      })
      .catch(() => {
        if (cancelled) return;
        setCandidateError(
          "Unable to load the people who may approve on this team."
        );
      });
    return () => {
      cancelled = true;
    };
  }, [candidateKeys]);

  /**
   * The steps as they will be written: an institution-wide step with one holder
   * *is* that holder, whether or not HR picked them from a list.
   *
   * A role that approves across the whole institution is held outside any one
   * team, so its holder could never be found by browsing this team's employees,
   * and choosing the role is the whole instruction — the backend appoints the
   * holder on save as well, so this only decides what the form shows. Resolved
   * while rendering rather than written into state, so a step is appointed the
   * moment its role and its single holder are both known — including when that
   * holder was already loaded for another step, where no new fetch would ever
   * arrive to notice it. Several holders stay a real choice and are left to HR.
   */
  const resolvedSections: DraftSection[] = useMemo(
    () =>
      sections.map((section) => {
        if (section.approver !== null) return section;
        if (roleByCode.get(section.approver_role)?.is_institution_wide !== true) {
          return section;
        }
        const roleId = roleIdByCode.get(section.approver_role);
        if (roleId === undefined || teamId === null) return section;
        const holders = candidates[`${teamId}:${roleId}`] ?? [];
        if (holders.length !== 1) return section;
        return { ...section, approver: holders[0].id };
      }),
    [candidates, teamId, roleIdByCode, roleByCode, sections]
  );

  /**
   * Everyone the eligible-approver lookups have returned, by id.
   *
   * Only used to name a person in a validation message. A step can be appointed
   * from a lookup that is no longer on screen, so the error names them from the
   * loaded set rather than guessing from the id.
   */
  const candidateNames = useMemo(() => {
    const byId = new Map<number, string>();
    for (const list of Object.values(candidates)) {
      for (const person of list) byId.set(person.id, person.full_name);
    }
    return byId;
  }, [candidates]);

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

  /**
   * The steps as the backend stores them: the role picked, and the person.
   *
   * The name is derived rather than typed, so the only thing HR has to get right
   * per step is the role and who acts for it. Every step has a role by
   * construction — "Add step" starts from the first role and is disabled when
   * there are no roles to choose from — so nothing here has to be filtered out.
   */
  /**
   * The value that appears twice across ``sections``, or null.
   *
   * Uniqueness is a workflow-level rule (one role, one person, one stage each), so
   * this compares the whole list rather than a pair at a time and names the repeat
   * rather than the two steps holding it: the steps are rendered as a numbered
   * list already, and the repeated role or person is the thing HR has to change.
   */
  function repeatOf<T>(sections: T[], key: (section: T) => string | null | undefined) {
    const seen = new Set<string>();
    for (const section of sections) {
      const value = key(section);
      if (value == null) continue;
      if (seen.has(value)) return value;
      seen.add(value);
    }
    return null;
  }

  function describeSteps(): TeamSectionInput[] {
    return resolvedSections.map((section) => ({
      name: roleLabelByCode.get(section.approver_role) ?? section.approver_role,
      approver_role: section.approver_role,
      ...(section.approver === null ? {} : { approver: section.approver }),
    }));
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

  async function save(draft: boolean) {
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

    // A team is handed to a manager the moment it exists. Only the person is
    // required: the designation is the team's own `manager` field, so no
    // team-scoped role has to exist for an institution-wide approver to run a
    // team. The manager is a create-only decision — an existing team's manager
    // is changed from its Approvers tab.
    if (!team) {
      const managerUser = Number(managerUserId) || 0;
      if (!managerUser) {
        setError(
          "Choose who will manage this team. Any active employee may be named, including an institution-wide approver."
        );
        setLoading(false);
        return;
      }
      input.manager = { user: managerUser };
    }

    const named = describeSteps();

    // Uniqueness is checked before anything else because the backend enforces it
    // as a constraint on the workflow: catching it here names the two steps, where
    // a database error naming a constraint would not. Runs on a draft too --
    // otherwise HR finds out about a repeated role only when they activate it.
    const repeatedRole = repeatOf(named, (section) => section.approver_role);
    if (repeatedRole) {
      setError(
        `Two steps both use the ${roleLabelByCode.get(repeatedRole) ?? repeatedRole} role. ` +
          "Give each step its own role, so one office cannot sign off twice on the same application."
      );
      setLoading(false);
      return;
    }
    const repeatedApprover = repeatOf(
      named.filter((section) => section.approver != null),
      (section) => String(section.approver)
    );
    if (repeatedApprover) {
      setError(
        `${candidateNames.get(Number(repeatedApprover)) ?? "The same person"} decides more than one step. ` +
          "Each step needs its own approver, so it is clear who signs at each point."
      );
      setLoading(false);
      return;
    }

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
      // An institution-wide step needs no pick: selecting its role appoints the
      // holder, and the backend writes them on save. Every other step is scoped
      // by the team, so a step nobody is named for blocks the save.
      //
      // A team that does not exist yet is the exception: it has no employees, so
      // there is nobody this form could offer. Naming somebody an approver as
      // the team is created does place them on it, but doing it from here would
      // mean listing the whole staff as if they were all eligible, which is the
      // thing the team-scoped picker exists to prevent. The steps are described
      // here and the people are appointed on the team's own page.
      const unstaffed = team
        ? resolvedSections.filter(
            (section) =>
              section.approver === null &&
              roleByCode.get(section.approver_role)?.is_institution_wide !== true
          )
        : [];
      if (unstaffed.length > 0) {
        setError(
          "Name the one person who decides at every step, or save the team as a draft."
        );
        setLoading(false);
        return;
      }
      // No chain name is sent: the backend names a new chain after the team and
      // keeps the existing one on an edit, so there is nothing for HR to decide
      // and nothing that can disagree between two people configuring one team.
      input.new_workflow = { sections: named };
    }

    try {
      const saved = team
        ? await updateTeam(team.id, input)
        : await createTeam(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        // The next screen is the roster, not the list: a team is people before
        // it is a chain, so a new team's workflow is configured from its page.
        router.push(
          team
            ? `/dashboard/teams/${team.id}`
            : `/dashboard/teams/${saved.id}?tab=members`
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

  /**
   * Page one is two different moves depending on the shape. On an edit it hands
   * over to page two without saving: the team already exists, so this page only
   * corrects it and the chain follows. A create also advances to page two, but
   * that page names the manager rather than describing a chain: the team does
   * not exist yet, so it has no chain to describe. The save happens there, and
   * writes a chainless draft whose Members tab is the next screen — the roster
   * has to exist before a step can be staffed from it.
   */
  function handleDetailsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (details.category === "academic" && details.campus === null) {
      setError(
        "An academic team sits at a campus. Choose one, or create it first — the campus is what makes campus-wide approvers reachable for this team's stages."
      );
      return;
    }
    setPage(2);
  }

  const backHref = team
    ? `/dashboard/teams/${team.id}`
    : "/dashboard/teams";

  if (page === 1) {
    return (
      <form
        id="team-details"
        onSubmit={handleDetailsSubmit}
        className="grid grid-cols-1 gap-4 md:grid-cols-2"
      >
        <div className="md:col-span-2">
          <FormProgress stages={stages} current="details" />
        </div>
        <div>
          <label
            htmlFor="name"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Name
          </label>
          <Input
            id="name"
            name="name"
            required
            value={details.name}
            onChange={(event) =>
              setDetails((current) => ({ ...current, name: event.target.value }))
            }
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
                { value: "administration" },
                { value: "academic" },
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
          <Input
            id="description"
            name="description"
            value={details.description}
            onChange={(event) =>
              setDetails((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
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
          <Input
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
          />
        </div>

        <div>
          <label
            htmlFor="effective_to"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            In force until
          </label>
          <Input
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
          />
        </div>

        {error && (
          <Alert tone="error" className="md:col-span-2">
            {error}
          </Alert>
        )}

        <div className="flex items-center gap-3 md:col-span-2">
          <Button type="submit" disabled={loading} loading={loading}>
            {team ? "Continue to approval steps" : "Continue to the manager"}
          </Button>
        {onCancel ? (
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href={backHref}
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
        </div>
      </form>
    );
  }

  if (!team) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <FormProgress stages={stages} current="manager" />
        </div>
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
        </div>

        {rolesError ? (
          <Alert tone="error" className="md:col-span-2">
            {rolesError}
          </Alert>
        ) : null}

        <div className="md:col-span-2">
          <label
            htmlFor="manager-user"
            className="mb-1 block text-sm font-medium text-text-primary"
          >
            Who runs this team?
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
                {employee.designation ? ` — ${employee.designation}` : ""}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-text-muted">
            Any active employee may run the team, including an institution-wide
            approver. They staff its roster, build its chains, and choose its
            default; HR keeps its identity and lifecycle.
          </p>
          {managerCandidates.length === 0 ? (
            <p className="mt-1 text-xs text-status-pending">
              No active employees with a record were found to name.
            </p>
          ) : null}
        </div>

        {error && (
          <Alert tone="error" className="md:col-span-2">
            {error}
          </Alert>
        )}

        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <Button
            onClick={() => void save(true)}
            disabled={loading}
            loading={loading}
          >
            Create team
          </Button>
          <Button variant="secondary" onClick={() => setPage(1)}>
            <ArrowLeft className="h-4 w-4" />
            Back to details
          </Button>
          {onCancel ? (
            <Button variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
          ) : (
            <Link
              href={backHref}
              className={buttonVariants({ variant: "secondary" })}
            >
              Cancel
            </Link>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <FormProgress stages={stages} current="steps" />
      </div>
      <div className="md:col-span-2">
        <p className="text-xs text-text-muted">
          <span className="font-medium text-text-secondary">
            {details.name || "This team"}
          </span>
          {details.campus === null ? "" : " — " + (campuses.find((campus) => campus.id === details.campus)?.name ?? "campus")}
        </p>
        <h3 className="mt-1 text-sm font-semibold text-text-primary">
          Who approves for this team
        </h3>
      </div>

      {rolesError ? (
        <Alert tone="error" className="md:col-span-2">
          {rolesError}
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 md:col-span-2">
        <span className="text-sm font-medium text-text-primary">Approval steps</span>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setShowNewRole((current) => !current)}
          >
            <Plus className="h-4 w-4" />
            New role
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              setSections((current) => [
                ...current,
                { approver_role: roles[0]?.code ?? "", approver: null },
              ])
            }
            disabled={rolesUnavailable}
          >
            <Plus className="h-4 w-4" />
            Add step
          </Button>
        </div>
      </div>

      {showNewRole ? (
        <div className="rounded-md border border-border-default bg-surface-muted p-3 md:col-span-2">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              aria-label="New role name"
              value={newRoleLabel}
              onChange={(event) => setNewRoleLabel(event.target.value)}
              placeholder="e.g. Team Supervisor"
              className="min-w-40 flex-1"
            />
            <Button
              onClick={() => void handleCreateRole()}
              disabled={creatingRole || newRoleLabel.trim() === ""}
              loading={creatingRole}
            >
              Save role
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setShowNewRole(false);
                setRoleCreateError("");
              }}
            >
              Cancel
            </Button>
          </div>
          {roleCreateError ? (
            <p className="mt-1 text-xs text-status-rejected">{roleCreateError}</p>
          ) : null}
        </div>
      ) : null}

      {candidateError ? (
        <Alert tone="error" className="md:col-span-2">
          {candidateError}
        </Alert>
      ) : null}

      {sections.length === 0 ? (
        <p className="text-sm text-text-muted md:col-span-2">No approval steps yet.</p>
      ) : null}

      {resolvedSections.map((section, index) => {
        const roleId = roleIdByCode.get(section.approver_role);
        const isInstitutionWide =
          roleByCode.get(section.approver_role)?.is_institution_wide === true;
        const options =
          teamId !== null && roleId ? candidates[`${teamId}:${roleId}`] ?? [] : [];
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
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={`Move step ${index + 1} up`}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={`Move step ${index + 1} down`}
                  disabled={index === sections.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown className="h-4 w-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={`Remove step ${index + 1}`}
                  onClick={() =>
                    setSections((current) =>
                      current.filter((_, i) => i !== index)
                    )
                  }
                  className="text-status-rejected"
                >
                  <X className="h-4 w-4" />
                </Button>
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
                disabled={options.length === 0}
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
              {isInstitutionWide ? (
                <p className="mt-1 text-xs text-text-muted">
                  Institution-wide role.{" "}
                  {options.length === 1
                    ? "Its holder approves automatically, wherever they sit."
                    : options.length === 0
                      ? "No active holder yet — appoint one on the Roles page."
                      : "Choose which holder decides at this step."}
                </p>
              ) : options.length === 0 ? (
                <p className="mt-1 text-xs text-text-muted">Nobody on this team can hold this role yet.</p>
              ) : null}
            </div>
          </div>
        );
      })}

      {error && (
        <Alert tone="error" className="md:col-span-2">
          {error}
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <Button
          onClick={() => void save(false)}
          disabled={loading}
          loading={loading}
        >
          {team ? "Save changes" : "Create team"}
        </Button>
        <Button
          variant="secondary"
          onClick={() => void save(true)}
          disabled={loading}
        >
          Save as draft
        </Button>
        <Button variant="secondary" onClick={() => setPage(1)}>
          <ArrowLeft className="h-4 w-4" />
          Back to details
        </Button>
        {onCancel ? (
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href={backHref}
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </div>
  );
}