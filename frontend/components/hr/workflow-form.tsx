"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowLeft, ArrowUp, Lock, X } from "lucide-react";

import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles-client";
import { getWorkflowMemberPool } from "@/lib/team-members-client";
import type { WorkflowMemberPool } from "@/lib/team-members";
import type { EligibleApprover } from "@/lib/teams";
import { listEligibleApprovers } from "@/lib/teams-client";
import type { Workflow, WorkflowInput, WorkflowSectionInput } from "@/lib/workflows";
import { createWorkflow, updateWorkflow } from "@/lib/workflows-client";

interface DraftStep {
  /** The role this step needs, by code. Open-ended, like every role code. */
  approver_role: string;
  /**
   * The one person appointed to the step, by user id. Null leaves it unstaffed.
   *
   * A team-wide or campus-wide role never writes a name here: its holder
   * approves without being appointed to the step, so the holding staffs it and
   * the screen shows the holder as a read-only answer. Only an institution-wide
   * role writes its holder here, because the save path appoints that holder and
   * has no other way to name them.
   */
  approver: number | null;
}

/**
 * One role's lone holder, by role id, from a list of holdings.
 *
 * A role with more than one holder maps to nothing: naming one of several as
 * the automatic answer is the ambiguity the backend refuses to resolve, so the
 * screen must leave it for HR too.
 */
function loneHolderMap<T extends { role: number; user: number; user_name: string }>(
  rows: T[]
): Map<number, { id: number; name: string }> {
  const lone = new Map<number, { id: number; name: string }>();
  const seen = new Set<number>();
  for (const row of rows) {
    if (seen.has(row.role)) {
      lone.delete(row.role);
      continue;
    }
    seen.add(row.role);
    lone.set(row.role, { id: row.user, name: row.user_name });
  }
  return lone;
}

/**
 * One chain, described end to end.
 *
 * A chain is written as the whole ordered step list rather than as a change to
 * one step, because a sequence that can be edited one row at a time can be
 * saved in a state nobody intended — two steps in the wrong order, a step left
 * with no role. What is written is what was described on screen.
 *
 * Who *acts* at each step is picked here, from the people the backend says may
 * be appointed. A second chain the team owns draws from the people not already
 * serving one of its chains (as a step approver or a normal member), so the
 * picker asks by team, role, and chain — the eligibility rule and the write
 * rule are the same one.
 */
export function WorkflowForm({
  workflow,
  team,
  roles,
  rolesError = "",
}: {
  workflow?: Workflow;
  team: { id: number; name: string; category?: string; campus?: number | null };
  roles: ApproverRole[];
  rolesError?: string;
}) {
  const router = useRouter();
  const [name, setName] = useState(workflow?.name ?? "");
  const [steps, setSteps] = useState<DraftStep[]>(() =>
    workflow
      ? workflow.sections.map((section) => ({
          approver_role: section.approver_role,
          approver: section.approver,
        }))
      : []
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pool, setPool] = useState<WorkflowMemberPool | null>(null);
  const [poolError, setPoolError] = useState("");
  const [memberIds, setMemberIds] = useState<number[]>(() =>
    (workflow?.members ?? []).map((member) => member.user)
  );
  const [candidates, setCandidates] = useState<Record<string, EligibleApprover[]>>(
    {}
  );
  const [candidateError, setCandidateError] = useState("");
  const [institutionHolders, setInstitutionHolders] = useState<RoleAssignment[]>(
    []
  );
  const [teamHolders, setTeamHolders] = useState<TeamRoleAssignment[]>([]);
  const [campusHolders, setCampusHolders] = useState<CampusRoleAssignment[]>([]);

  const roleByCode = useMemo(
    () => new Map(roles.map((role) => [role.code, role])),
    [roles]
  );
  const roleIdByCode = useMemo(
    () => new Map(roles.map((role) => [role.code, role.id])),
    [roles]
  );
  const roleById = useMemo(
    () => new Map(roles.map((role) => [role.id, role])),
    [roles]
  );

  /**
   * The single institution-wide holder of each role, name and all, by role id.
   * A role with no holder — or more than one — maps to nothing, because naming
   * one of several people as the automatic answer is exactly the ambiguity the
   * backend leaves unstaffed rather than guess at.
   */
  const institutionHolderByRoleId = useMemo(
    () => loneHolderMap(institutionHolders),
    [institutionHolders]
  );

  /** The holder a role has on *this* team, when the team holds one. */
  const teamWideHolderByRoleId = useMemo(
    () => loneHolderMap(teamHolders.filter((holding) => holding.team === team.id)),
    [teamHolders, team.id]
  );

  /** The holder a role has at *this* team's campus, for an academic team. */
  const campusWideHolderByRoleId = useMemo(() => {
    if (team.campus == null) {
      return new Map<number, { id: number; name: string }>();
    }
    return loneHolderMap(
      campusHolders.filter((holding) => holding.campus === team.campus)
    );
  }, [campusHolders, team.campus]);

  /**
   * Roles another team or campus holds wide.
   *
   * A wide role is scoped to the team or campus that holds it: its holder
   * approves for that group's people, not for everybody's. So a role claimed
   * elsewhere is that team's or campus's to use and is not offered here. A plain
   * role — held wide nowhere — belongs to no scope and is offered everywhere.
   */
  const wideElsewhereRoleIds = useMemo(() => {
    const ids = new Set<number>();
    for (const holding of teamHolders) {
      if (holding.team !== team.id) ids.add(holding.role);
    }
    for (const holding of campusHolders) {
      if (team.campus == null || holding.campus !== team.campus) {
        ids.add(holding.role);
      }
    }
    return ids;
  }, [teamHolders, campusHolders, team.id, team.campus]);

  /** How a wide role resolves for this team, if it is wide for this team. */
  function wideScopeFor(role: ApproverRole):
    | {
        holder: { id: number; name: string };
        scope: "team" | "campus" | "institution";
      }
    | undefined {
    const teamWide = teamWideHolderByRoleId.get(role.id);
    if (teamWide) return { holder: teamWide, scope: "team" };
    const campusWide = campusWideHolderByRoleId.get(role.id);
    if (campusWide) return { holder: campusWide, scope: "campus" };
    if (role.is_institution_wide && team.category === "administration") {
      const institutionWide = institutionHolderByRoleId.get(role.id);
      if (institutionWide) {
        return { holder: institutionWide, scope: "institution" };
      }
    }
    return undefined;
  }

  /**
   * The roles this team may put on a step.
   *
   * A wide role is scoped to where it reaches: an institution-wide role only
   * serves an administration team, a team-wide role only the team that holds
   * it, and a campus-wide role only the academic teams at its campus. A plain
   * role — held wide nowhere — belongs to no scope and serves every team.
   */
  const offeredRoles = useMemo(
    () =>
      roles.filter((role) => {
        if (teamWideHolderByRoleId.has(role.id)) return true;
        if (campusWideHolderByRoleId.has(role.id)) return true;
        if (role.is_institution_wide) return team.category === "administration";
        return !wideElsewhereRoleIds.has(role.id);
      }),
    [
      roles,
      team.category,
      teamWideHolderByRoleId,
      campusWideHolderByRoleId,
      wideElsewhereRoleIds,
    ]
  );

  /**
   * The chain this form is shaping, as the eligible-approver question needs it:
   * the chain's own id when editing an existing one so its current staff are
   * offered, or the ``new`` sentinel while configuring one that does not exist
   * yet so nobody already serving one of the team's chains is offered.
   */
  const workflowScope = workflow?.id ?? ("new" as const);

  /**
   * The team and roles a fetch is needed for, as a stable string so that adding,
   * reordering or re-picking a step's role does not re-ask the same question on
   * every change. The chain scope is constant for the form's life, so it is not
   * part of the key.
   */
  const candidateKeys = useMemo(() => {
    const roleIds = new Set<number>();
    steps.forEach((step) => {
      const roleId = roleIdByCode.get(step.approver_role);
      if (roleId !== undefined) roleIds.add(roleId);
    });
    return [...roleIds].map((roleId) => `${team.id}:${roleId}`).join(",");
  }, [steps, team.id, roleIdByCode]);

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
          Number(rolePart),
          workflowScope
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
        setCandidateError("Unable to load the people who may approve here.");
      });
    return () => {
      cancelled = true;
    };
  }, [candidateKeys, workflowScope]);

  /**
   * Read who already holds each role wide: institution-wide, on this team, and
   * at this team's campus.
   *
   * The screen needs all three scopes. A wide holding is what makes a broad role
   * usable for a given team at all, so the role list is scoped from these and
   * the holder is shown on the step rather than asked for.
   *
   * The institution-wide holder is also appointed at save, so the form fills
   * that one in itself — mirroring the backend's rule exactly: only an
   * institution-wide role, only an administration team (an academic team may
   * not use an institution-wide approver at all), and only when there is exactly
   * one holder. Team-wide and campus-wide steps stay unstaffed in the payload:
   * those resolve without an appointment, so writing a name is the one thing the
   * save path would refuse.
   *
   * Unreadable holdings are treated as "none": the field is then left to HR,
   * which is precisely what the save path does when it cannot appoint either.
   */
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listRoleAssignments(),
      listTeamRoleAssignments(),
      listCampusRoleAssignments(),
    ])
      .then(([institution, teams, campuses]) => {
        if (cancelled) return;
        setInstitutionHolders(institution);
        setTeamHolders(teams);
        setCampusHolders(campuses);
        const lone = loneHolderMap(institution);
        setSteps((current) => {
          let changed = false;
          const next = current.map((step) => {
            const role = step.approver_role
              ? roleByCode.get(step.approver_role)
              : undefined;
            if (role === undefined || !role.is_institution_wide) return step;
            if (team.category !== "administration") return step;
            const holder = lone.get(role.id);
            if (holder === undefined) return step;
            if (step.approver === holder.id) return step;
            changed = true;
            return { ...step, approver: holder.id };
          });
          return changed ? next : current;
        });
      })
      .catch(() => {
        // No visible holdings means no auto-appointment and every role treated
        // as plain; HR can still pick by hand.
      });
    return () => {
      cancelled = true;
    };
    // Roles and the team's category are constant for the form's life, so the
    // effect runs only once; they are listed for the linter, not to re-run it.
  }, [roleByCode, team.category]);

  useEffect(() => {
    let cancelled = false;
    getWorkflowMemberPool(team.id, workflow?.id)
      .then((data) => {
        if (cancelled) return;
        setPool(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setPoolError(
          err instanceof Error
            ? err.message
            : "Could not load the workflow's member pool."
        );
      });
    return () => {
      cancelled = true;
    };
  }, [team.id, workflow?.id]);

  const selectedIds = new Set(memberIds);

function toggleMember(userId: number) {
    setMemberIds((current) =>
      current.includes(userId)
        ? current.filter((id) => id !== userId)
        : [...current, userId]
    );
  }

  const peopleById = new Map<
    number,
    { user: number; full_name: string; email: string; designation: string }
  >();
  for (const person of [
    ...(pool?.available ?? []),
    ...(pool?.current ?? []),
    ...(pool?.assigned_elsewhere ?? []),
  ]) {
    peopleById.set(person.user, person);
  }
  for (const member of workflow?.members ?? []) {
    if (!peopleById.has(member.user)) {
      // The embedded member carries the person's display fields only, so
      // designation is left blank rather than read from a field it never sends.
      peopleById.set(member.user, {
        user: member.user,
        full_name: member.full_name,
        email: member.email,
        designation: "",
      });
    }
  }
  const addable = (pool?.available ?? []).filter(
    (person) => !selectedIds.has(person.user)
  );
  const elsewhere = pool?.assigned_elsewhere ?? [];

  function move(index: number, direction: -1 | 1) {
    setSteps((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function remove(index: number) {
    setSteps((current) => current.filter((_, position) => position !== index));
  }

  function setApprover(index: number, approver: number | null) {
    setSteps((current) =>
      current.map((step, position) =>
        position === index ? { ...step, approver } : step
      )
    );
  }

  /**
   * Re-reads the people for one step when its role changes, because the person
   * chosen for the previous role is very likely not eligible for the new one —
   * and sending an ineligible id would earn a refusal on save. The picker
   * refetches through the role-based candidate keys above.
   *
   * An institution-wide role also staffs its own step the moment it is chosen:
   * it is the single holder who will be appointed at save, so the field shows
   * that answer now rather than a step that looks undecided. A team-wide or
   * campus-wide role is shown with its holder too, but the step stays unstaffed
   * here — those resolve without an appointment, so a name written here is the
   * one thing the save path would refuse.
   */
  function changeRole(index: number, approverRole: string) {
    setSteps((current) =>
      current.map((step, position) => {
        if (position !== index) return step;
        const next = {
          ...step,
          approver_role: approverRole,
          approver: null,
        };
        const role = roleByCode.get(approverRole);
        const wide = role ? wideScopeFor(role) : undefined;
        if (wide?.scope === "institution") {
          return { ...next, approver: wide.holder.id };
        }
        return next;
      })
    );
  }

  function addStep() {
    setSteps((current) => {
      const approverRole = offeredRoles[0]?.code ?? "";
      const role = roleByCode.get(approverRole);
      const wide = role ? wideScopeFor(role) : undefined;
      const approver = wide?.scope === "institution" ? wide.holder.id : null;
      return [...current, { approver_role: approverRole, approver }];
    });
  }

  /** One role may sit at only one point in a chain. */
  function repeatedRole(): string | null {
    const seen = new Set<string>();
    for (const step of steps) {
      if (!step.approver_role) continue;
      if (seen.has(step.approver_role)) return step.approver_role;
      seen.add(step.approver_role);
    }
    return null;
  }

  function describe(): WorkflowSectionInput[] {
    return steps.map((step, index) => ({
      order: index + 1,
      approver_role: step.approver_role,
      approver: step.approver,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    if (!name.trim()) {
      setError(
        "Give this chain its own name. It is what the team's chain list and the audit trail call it, so it cannot be left blank."
      );
      setLoading(false);
      return;
    }
    if (steps.length === 0) {
      setError("A chain needs at least one step before it can be saved.");
      setLoading(false);
      return;
    }
    if (steps.some((step) => !step.approver_role)) {
      setError("Every step needs a role. Pick one for each step.");
      setLoading(false);
      return;
    }
    const repeated = repeatedRole();
    if (repeated) {
      setError(
        `Two steps both use the ${roleByCode.get(repeated)?.label ?? repeated} role. ` +
          "Give each step its own role, so one office cannot sign off twice on the same application."
      );
      setLoading(false);
      return;
    }

    const input: WorkflowInput = {
      name: name.trim(),
      team: team.id,
      sections: describe(),
      members: memberIds,
    };

    try {
      if (workflow) {
        await updateWorkflow(workflow.id, input);
      } else {
        await createWorkflow(input);
      }
      router.push(`/dashboard/teams/${team.id}/workflows`);
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

  /** The names of the people currently appointed to this chain's steps, by id. */
  const approverNameById = new Map<number, string>();
  for (const section of workflow?.sections ?? []) {
    if (section.approver != null && section.approver_name) {
      approverNameById.set(section.approver, section.approver_name);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="workflow_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="workflow_name"
          name="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder={`e.g. ${team.name} replacement`}
        />
        <p className="mt-1 text-xs text-text-muted">
          This chain&apos;s own name — what the team&apos;s chain list and the
          audit trail call it. It applies from today until the end of the current
          academic calendar.
        </p>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">Steps</span>
          <button
            type="button"
            onClick={addStep}
            disabled={offeredRoles.length === 0}
            className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            Add step
          </button>
        </div>

        {rolesError && (
          <p className="mb-2 text-xs text-status-rejected">{rolesError}</p>
        )}
        {candidateError && (
          <p className="mb-2 text-xs text-status-rejected">{candidateError}</p>
        )}
        {roles.length === 0 && (
          <p className="mb-2 text-xs text-status-pending">
            No approver roles are available, so no step can be described. Create
            a role first.
          </p>
        )}
        {roles.length > 0 && offeredRoles.length === 0 && (
          <p className="mb-2 text-xs text-status-pending">
            No approver role applies to this team: the roles available are held
            team-wide, campus-wide, or institution-wide somewhere they do not
            reach here. Give a role a holding this team can use, or create one
            for it.
          </p>
        )}

        {steps.length === 0 ? (
          <p className="rounded-md border border-dashed border-border-default p-4 text-sm text-text-muted">
            No steps yet. Each step is one office deciding once, in order —
            the chain reads from the top down.
          </p>
        ) : (
          <ol className="space-y-2">
            {steps.map((step, index) => {
              const roleId = roleIdByCode.get(step.approver_role);
              const people =
                roleId === undefined
                  ? []
                  : (candidates[`${team.id}:${roleId}`] ?? []);
              // An appointed approver must stay visible and selectable even if
              // they are not in the fetched pool any more (e.g. the step's
              // role changed since they were appointed, or they left the team's
              // pool after the appointment).
              const optionPeople =
                step.approver != null &&
                !people.some((person) => person.id === step.approver)
                  ? [
                      ...people,
                      {
                        id: step.approver,
                        full_name: approverNameById.get(step.approver) ?? "Current approver",
                        email: "",
                        designation: "",
                      },
                    ]
                  : people;
              // A wide role is staffed by its holding rather than by a name here.
              // An institution-wide role's holder is the one true approver, so
              // the field is locked to that name and another may not be selected
              // — the backend appoints the same person at save. A team-wide or
              // campus-wide role's holder resolves the step without an
              // appointment, so the step is shown staffed but is left unstaffed
              // in what is sent.
              const role =
                roleId === undefined ? undefined : roleById.get(roleId);
              const wide = role ? wideScopeFor(role) : undefined;
              // The selected role stays visible even when it is no longer
              // offered for this team — an existing chain edited after a wide
              // holding moved still has to show the role it uses.
              const options = offeredRoles.some(
                (candidate) => candidate.code === step.approver_role
              )
                ? offeredRoles
                : role
                  ? [role, ...offeredRoles]
                  : offeredRoles;
              return (
              <li
                key={index}
                className="flex flex-wrap items-end gap-2 rounded-md border border-border-default bg-surface-page p-3"
              >
                <span className="w-6 shrink-0 pb-2 text-sm font-medium text-text-muted">
                  {index + 1}
                </span>
                <div className="min-w-44 flex-1">
                  <label
                    htmlFor={`step-role-${index}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    Role
                  </label>
                  <select
                    id={`step-role-${index}`}
                    value={step.approver_role}
                    onChange={(event) =>
                      changeRole(index, event.target.value)
                    }
                    className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
                  >
                    {options.map((role) => {
                      const usedIndex = steps.findIndex(
                        (step) => step.approver_role === role.code
                      );
                      const usedElsewhere =
                        usedIndex !== -1 && usedIndex !== index;
                      return (
                        <option
                          key={role.id}
                          value={role.code}
                          disabled={usedElsewhere}
                        >
                          {role.label}
                          {role.is_institution_wide
                            ? " (institution-wide)"
                            : ""}
                          {usedElsewhere
                            ? ` — used in step ${usedIndex + 1}`
                            : ""}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div className="min-w-40 flex-1">
                  <label
                    htmlFor={`step-approver-${index}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    Approver
                  </label>
                  {wide ? (
                    <>
                      <div
                        id={`step-approver-${index}`}
                        className="flex items-center gap-2 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary"
                      >
                        <Lock className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                        <span className="font-medium">{wide.holder.name}</span>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">
                        {wide.scope === "institution"
                          ? "Locked to the institution-wide holder of this role."
                          : wide.scope === "team"
                            ? "Locked to the team-wide holder of this role."
                            : "Locked to the campus-wide holder of this role."}
                      </p>
                    </>
                  ) : (
                    <select
                      id={`step-approver-${index}`}
                      value={step.approver ?? ""}
                      onChange={(event) =>
                        setApprover(
                          index,
                          event.target.value ? Number(event.target.value) : null
                        )
                      }
                      disabled={roleId === undefined}
                      className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <option value="">
                        {step.approver != null
                          ? approverNameById.get(step.approver) ?? "Not appointed yet"
                          : people.length > 0
                            ? "Not appointed yet"
                            : roleId === undefined
                              ? "Pick a role first"
                              : "Nobody may be appointed here yet"}
                      </option>
                      {optionPeople.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.full_name}
                          {person.designation ? ` — ${person.designation}` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="flex items-center gap-1 pb-1">
                  <button
                    type="button"
                    aria-label={`Move step ${index + 1} earlier`}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                    className="rounded-md border border-border-default p-1.5 text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Move step ${index + 1} later`}
                    disabled={index === steps.length - 1}
                    onClick={() => move(index, 1)}
                    className="rounded-md border border-border-default p-1.5 text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove step ${index + 1}`}
                    onClick={() => remove(index)}
                    className="rounded-md border border-border-default p-1.5 text-text-secondary hover:bg-button-secondary-hover"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
              );
            })}
          </ol>
        )}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">
            Normal workflow members
          </span>
        </div>
        <p className="mb-3 text-xs text-text-muted">
          Drawn only from this team&apos;s members on the{" "}
          <a
            href={`/dashboard/teams/${team.id}?tab=members`}
            className="font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            Members
          </a>{" "}
          tab: the team members whose submissions this chain decides. Each
          person serves one of the team&apos;s chains at a time, and adding
          them to a team never places them on a chain by itself. Distinct from
          the step approvers above — members submit into the chain, approvers
          act at its steps.
        </p>

        {poolError && <p className="mb-2 text-sm text-status-rejected">{poolError}</p>}

        {!pool && !poolError && (
          <p className="rounded-md border border-dashed border-border-default p-4 text-sm text-text-muted">
            Loading who may join this chain&apos;s member pool...
          </p>
        )}

        {pool && (
          <div className="space-y-3">
            {memberIds.length > 0 ? (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  On this chain ({memberIds.length})
                </p>
                <ul className="mt-1 divide-y divide-border-default rounded-md border border-border-default">
                  {memberIds.map((userId) => {
                    const person = peopleById.get(userId);
                    return (
                      <li
                        key={userId}
                        className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-text-primary">
                            {person?.full_name ?? "Member"}
                          </p>
                          <p className="text-xs text-text-muted">
                            {[person?.designation ?? "", person?.email ?? ""]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => toggleMember(userId)}
                          className="rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover"
                        >
                          Remove
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <p className="rounded-md border border-dashed border-border-default p-3 text-sm text-text-muted">
                Nobody is on this chain as a normal member yet.
              </p>
            )}

            {addable.length > 0 ? (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Team members who can join
                </p>
                <ul className="mt-1 divide-y divide-border-default rounded-md border border-border-default">
                  {addable.map((person) => (
                    <li
                      key={person.user}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                    >
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {person.full_name}
                        </p>
                        <p className="text-xs text-text-muted">
                          {[person.designation, person.email]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleMember(person.user)}
                        className="rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover"
                      >
                        Add
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-text-muted">
                No other team member may join this chain — the pool is limited
                to {team.name}&apos;s members who are not already on another
                chain with the team.
              </p>
            )}

            {elsewhere.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Already on another chain of this team
                </p>
                <ul className="mt-1 divide-y divide-border-default rounded-md border border-border-default">
                  {elsewhere.map((person) => (
                    <li
                      key={person.user}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                    >
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {person.full_name}
                        </p>
                        <p className="text-xs text-text-muted">
                          On {person.workflow_name}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {error && <p className="text-sm text-status-rejected">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          disabled={loading || offeredRoles.length === 0}
          className="rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading
            ? "Saving..."
            : workflow
              ? "Save workflow"
              : "Create workflow"}
        </button>
        <button
          type="button"
          onClick={() =>
            router.push(
              workflow
                ? `/dashboard/teams/${team.id}/workflows`
                : `/dashboard/teams/${team.id}/workflows`
            )
          }
          className="inline-flex items-center gap-1 rounded-md border border-border-default bg-button-secondary px-3 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Cancel
        </button>
      </div>

      <p className="text-xs text-text-muted">
        A second chain the team owns draws its step approvers and members from
        the people not already serving one of its chains — one employee serves
        one chain at a time, unless they are a team-wide, campus-wide, or
        institution-wide approver.
      </p>
    </form>
  );
}
