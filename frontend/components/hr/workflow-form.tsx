"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowLeft, ArrowUp, Lock, X } from "lucide-react";

import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import { listRoleAssignments } from "@/lib/approver-roles-client";
import { getWorkflowMemberPool } from "@/lib/team-members-client";
import type { WorkflowMemberPool } from "@/lib/team-members";
import type { EligibleApprover } from "@/lib/teams";
import { listEligibleApprovers } from "@/lib/teams-client";
import type { Workflow, WorkflowInput, WorkflowSectionInput } from "@/lib/workflows";
import { createWorkflow, updateWorkflow } from "@/lib/workflows-client";

interface DraftStep {
  /** The role this step needs, by code. Open-ended, like every role code. */
  approver_role: string;
  /** Only set when HR has overridden the step's name from the role's label. */
  name?: string;
  /** The one person appointed to the step, by user id. Null leaves it unstaffed. */
  approver: number | null;
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
  team: { id: number; name: string; category?: string };
  roles: ApproverRole[];
  rolesError?: string;
}) {
  const router = useRouter();
  const [name, setName] = useState(workflow?.name ?? "");
  const [steps, setSteps] = useState<DraftStep[]>(() =>
    workflow
      ? workflow.sections.map((section) => ({
          approver_role: section.approver_role,
          name: section.name,
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
  const [wideHolders, setWideHolders] = useState<RoleAssignment[]>([]);

  const roleByCode = useMemo(
    () => new Map(roles.map((role) => [role.code, role])),
    [roles]
  );
  const roleIdByCode = useMemo(
    () => new Map(roles.map((role) => [role.code, role.id])),
    [roles]
  );

  /**
   * The single institution-wide holder of each role, name and all, by role id.
   * A role with no holder — or more than one — maps to nothing, because naming
   * one of several people as the automatic answer is exactly the ambiguity the
   * backend leaves unstaffed rather than guess at. The name is here because a
   * locked approver field shows it read-only; it is not a candidate to pick
   * from.
   */
  const wideHolderByRoleId = useMemo(() => {
    const lone = new Map<number, { id: number; name: string }>();
    const seen = new Set<number>();
    for (const assignment of wideHolders) {
      if (seen.has(assignment.role)) {
        lone.delete(assignment.role);
        continue;
      }
      seen.add(assignment.role);
      lone.set(assignment.role, {
        id: assignment.user,
        name: assignment.user_name,
      });
    }
    return lone;
  }, [wideHolders]);

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
   * Read who already holds each role institution-wide. The backend appoints
   * that holder at save, so the form needs the same answer on first draw.
   * Unreadable holdings are treated as "none": the field is then left to HR,
   * which is precisely what the save path does when it cannot appoint either.
   *
   * The fill when the list arrives mirrors the backend's rule exactly and is
   * deliberately as narrow: only an institution-wide role, only an
   * administration team (an academic team may not use an institution-wide
   * approver at all), and only when there is exactly one holder. That answer is
   * the one true approver of the step — the field is locked to it and another
   * name may not be selected — so the fill also corrects a person appointed
   * before this rule existed: the wide holder wins.
   */
  useEffect(() => {
    let cancelled = false;
    listRoleAssignments()
      .then((assignments) => {
        if (cancelled) return;
        setWideHolders(assignments);
        const lone = new Map<number, { id: number; name: string }>();
        const seen = new Set<number>();
        for (const assignment of assignments) {
          if (seen.has(assignment.role)) {
            lone.delete(assignment.role);
            continue;
          }
          seen.add(assignment.role);
          lone.set(assignment.role, {
            id: assignment.user,
            name: assignment.user_name,
          });
        }
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
        // No visible holders means no auto-appointment; HR still picks by hand.
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

  function update(index: number, patch: Partial<DraftStep>) {
    setSteps((current) =>
      current.map((step, position) =>
        position === index ? { ...step, ...patch } : step
      )
    );
  }

  /**
   * Re-reads the people for one step when its role changes, because the person
   * chosen for the previous role is very likely not eligible for the new one —
   * and sending an ineligible id would earn a refusal on save. The picker
   * refetches through the role-based candidate keys above.
   *
   * An institution-wide role also staffs its own step the moment it is
   * chosen: it is the single holder who will be appointed at save, so the
   * field shows that answer now rather than a step that looks undecided.
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
        if (role?.is_institution_wide && team.category === "administration") {
          const holder = wideHolderByRoleId.get(role.id);
          if (holder !== undefined) {
            return { ...next, approver: holder.id };
          }
        }
        return next;
      })
    );
  }

  function addStep() {
    setSteps((current) => {
      const approverRole = roles[0]?.code ?? "";
      const role = roleByCode.get(approverRole);
      const approver =
        role?.is_institution_wide && team.category === "administration"
          ? (wideHolderByRoleId.get(role.id)?.id ?? null)
          : null;
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
      ...(step.name ? { name: step.name } : {}),
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
      router.push(`/organisation/teams/${team.id}/workflows`);
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
            disabled={roles.length === 0}
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
              // An institution-wide role has one true approver — its single
              // institution-wide holder — so the field is locked to that name
              // and another may not be selected. The backend appoints the same
              // person at save, so the lock is the front half of a rule the
              // whole chain already keeps.
              const wideHolder =
                roleId !== undefined && team.category === "administration"
                  ? wideHolderByRoleId.get(roleId)
                  : undefined;
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
                    {roles.map((role) => {
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
                    htmlFor={`step-name-${index}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    Step name
                  </label>
                  <input
                    id={`step-name-${index}`}
                    value={step.name ?? ""}
                    onChange={(event) =>
                      update(index, {
                        name: event.target.value || undefined,
                      })
                    }
                    className="w-full rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
                    placeholder={
                      roleByCode.get(step.approver_role)?.label ?? "Role label"
                    }
                  />
                </div>
                <div className="min-w-40 flex-1">
                  <label
                    htmlFor={`step-approver-${index}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    Approver
                  </label>
                  {wideHolder ? (
                    <>
                      <div
                        id={`step-approver-${index}`}
                        className="flex items-center gap-2 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary"
                      >
                        <Lock className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                        <span className="font-medium">{wideHolder.name}</span>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">
                        Locked to the institution-wide holder of this role.
                      </p>
                    </>
                  ) : (
                    <select
                      id={`step-approver-${index}`}
                      value={step.approver ?? ""}
                      onChange={(event) =>
                        update(index, {
                          approver: event.target.value
                            ? Number(event.target.value)
                            : null,
                        })
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
            href={`/organisation/teams/${team.id}?tab=members`}
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
          disabled={loading || roles.length === 0}
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
                ? `/organisation/teams/${team.id}/workflows`
                : `/organisation/teams/${team.id}/workflows`
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
