"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowLeft, ArrowUp, Lock, Plus, X } from "lucide-react";

import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  createOrReuseApproverRole,
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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/states";

interface DraftStep {
  /** The role this step needs, by code. Open-ended, like every role code. */
  approver_role: string;
  /** The one person appointed to the step, by user id. Null leaves it unstaffed. */
  approver: number | null;
}

/** The single person a wide holding places on a step, name and all. */
interface WideHolder {
  id: number;
  name: string;
}

/**
 * One holder per role, dropping any role that somehow has more.
 *
 * Every wide holding is unique per (scope, role), so more than one is not
 * reachable today. Mapping it to nothing is still the right answer: naming one
 * of several people as the automatic approver is the ambiguity the backend
 * leaves unstaffed rather than guess at.
 */
function loneHolderByRole(
  assignments: {
    role: number;
    user: number;
    user_name: string;
  }[]
): Map<number, WideHolder> {
  const lone = new Map<number, WideHolder>();
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
  // Seeded once from the page's list; roles created from the "New role" card
  // are folded in below, so a manager who adds a role can put it on a step
  // without reloading the form. The prop itself is fixed for the form's life.
  const [availableRoles, setAvailableRoles] = useState<ApproverRole[]>(roles);
  const [roleDialogOpen, setRoleDialogOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [roleDialogError, setRoleDialogError] = useState("");
  const [roleNotice, setRoleNotice] = useState("");
  const [creatingRole, setCreatingRole] = useState(false);
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
    () => new Map(availableRoles.map((role) => [role.code, role])),
    [availableRoles]
  );
  const roleById = useMemo(
    () => new Map(availableRoles.map((role) => [role.id, role])),
    [availableRoles]
  );
  const roleIdByCode = useMemo(
    () => new Map(availableRoles.map((role) => [role.code, role.id])),
    [availableRoles]
  );

  /**
   * The single holder of each role at each scope, narrowest first.
   *
   * A step is staffed by the narrowest wide holding that applies — the team's
   * own holder, then the holder at the team's campus, then the institution-wide
   * holder for an administration team — which is the same precedence the
   * backend resolves by at submission (``chains.providers``). Merging widest
   * first (institution, campus, team) leaves the narrowest holding in place, so
   * the field shows the one person the backend would route to rather than any
   * of the people who could theoretically staff it.
   *
   * The name is here because a locked approver field shows it read-only; it is
   * not a candidate to pick from.
   */
  const wideHolderByRoleId = useMemo(() => {
    const merged = new Map<number, WideHolder>();
    for (const [roleId, holder] of loneHolderByRole(institutionHolders)) {
      const role = roleById.get(roleId);
      // An institution-wide approver is an administration office: an academic
      // team may not use one at all, so its holder never staffs that step.
      if (role?.is_institution_wide && team.category === "administration") {
        merged.set(roleId, holder);
      }
    }
    for (const [roleId, holder] of loneHolderByRole(campusHolders)) {
      // A campus-wide holding reaches only the academic teams at its own
      // campus, so an administration team never staffs a step from it.
      if (team.category === "academic") {
        merged.set(roleId, holder);
      }
    }
    for (const [roleId, holder] of loneHolderByRole(teamHolders)) {
      merged.set(roleId, holder);
    }
    return merged;
  }, [teamHolders, campusHolders, institutionHolders, roleById, team.category]);

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
   * Read who holds each role wide, at every scope that can staff this team.
   *
   * The backend resolves a step to the narrowest holding, so the form needs all
   * three lists to show the same answer. A manager may read each of them
   * (granting or moving a holding stays HR's), so the lock below is the same one
   * HR sees rather than a manager-only gap. An unreadable list is treated as
   * "none": that step is left to the picker, which is what the save path does
   * when it cannot resolve a holder either.
   */
  useEffect(() => {
    let cancelled = false;
    listTeamRoleAssignments(team.id)
      .then((rows) => {
        if (!cancelled) setTeamHolders(rows);
      })
      .catch(() => {
        // No visible team-wide holders means no lock from this scope.
      });
    listRoleAssignments()
      .then((rows) => {
        if (!cancelled) setInstitutionHolders(rows);
      })
      .catch(() => {
        // No visible institution-wide holders means no lock from this scope.
      });
    if (team.campus != null) {
      listCampusRoleAssignments(team.campus)
        .then((rows) => {
          if (!cancelled) setCampusHolders(rows);
        })
        .catch(() => {
          // No visible campus-wide holders means no lock from this scope.
        });
    }
    return () => {
      cancelled = true;
    };
  }, [team.id, team.campus]);

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
        full_name: member.user_name,
        email: member.user_email,
        designation: member.designation ?? "",
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
   * A role with a wide holder also staffs its own step the moment it is chosen:
   * that is the single person who will be written at save, so the field shows
   * the answer now rather than a step that looks undecided.
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
        if (role !== undefined) {
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
      const approverRole = availableRoles[0]?.code ?? "";
      const role = roleByCode.get(approverRole);
      const approver =
        role !== undefined
          ? (wideHolderByRoleId.get(role.id)?.id ?? null)
          : null;
      return [...current, { approver_role: approverRole, approver }];
    });
  }

  /**
   * Add a role from the step form, or use the one that already has that name.
   *
   * The list is not HR's only any more: a manager describing their own chain
   * can add the office their steps need, and the backend dedupes by name so the
   * organisation still has one "Dean" rather than one per team. The returned
   * role is folded into the local list, which is what makes it selectable in
   * the step that prompted the card.
   */
  async function createRole() {
    const label = newRoleName.trim();
    if (!label) {
      setRoleDialogError("Enter a role name.");
      return;
    }
    setRoleDialogError("");
    setCreatingRole(true);
    try {
      const { role, created } = await createOrReuseApproverRole(label);
      setAvailableRoles((current) => {
        if (current.some((row) => row.id === role.id)) {
          return current.map((row) => (row.id === role.id ? role : row));
        }
        return [...current, role].sort((a, b) => a.label.localeCompare(b.label));
      });
      setRoleNotice(
        created
          ? `Added ${role.label}.`
          : `${role.label} already exists — using it.`
      );
      setNewRoleName("");
      setRoleDialogOpen(false);
    } catch (err) {
      setRoleDialogError(
        err instanceof Error ? err.message : "Could not create the role."
      );
    } finally {
      setCreatingRole(false);
    }
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
    return steps.map((step, index) => {
      const role = step.approver_role
        ? roleByCode.get(step.approver_role)
        : undefined;
      // A wide holding is the step's approver even though it was never picked
      // in the select: the field shows it locked, and the same person is sent.
      const holder =
        role !== undefined ? wideHolderByRoleId.get(role.id) : undefined;
      return {
        order: index + 1,
        approver_role: step.approver_role,
        approver: holder?.id ?? step.approver,
      };
    });
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
        <Input
          id="workflow_name"
          name="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          placeholder={`e.g. ${team.name} replacement`}
        />
      </div>

      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium text-text-primary">Steps</span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={() => {
                setRoleDialogError("");
                setNewRoleName("");
                setRoleDialogOpen(true);
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              New role
            </Button>
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={addStep}
              disabled={availableRoles.length === 0}
            >
              Add step
            </Button>
          </div>
        </div>

        {rolesError && (
          <p className="mb-2 text-xs text-status-rejected">{rolesError}</p>
        )}
        {candidateError && (
          <p className="mb-2 text-xs text-status-rejected">{candidateError}</p>
        )}
        {roleNotice && (
          <p className="mb-2 text-xs text-status-approved">{roleNotice}</p>
        )}
        {availableRoles.length === 0 && (
          <p className="mb-2 text-xs text-status-pending">
            No approver roles yet. Use “New role” to add one.
          </p>
        )}

        {steps.length === 0 ? (
          <p className="rounded-md border border-dashed border-border-default p-4 text-sm text-text-muted">
            No steps yet.
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
              // A role with a wide holder has one true approver — the
              // narrowest holder of that role for this team — so the field is
              // locked to that name and another may not be selected.
              const wideHolder =
                roleId !== undefined
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
                    {availableRoles.map((role) => {
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
                  {wideHolder ? (
                    <div
                      id={`step-approver-${index}`}
                      className="flex items-center gap-2 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary"
                    >
                      <Lock className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                      <span className="font-medium">{wideHolder.name}</span>
                    </div>
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
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={`Move step ${index + 1} earlier`}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={`Move step ${index + 1} later`}
                    disabled={index === steps.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={`Remove step ${index + 1}`}
                    onClick={() => remove(index)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
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

        {poolError && <p className="mb-2 text-sm text-status-rejected">{poolError}</p>}

        {!pool && !poolError && (
          <p className="rounded-md border border-dashed border-border-default p-4 text-sm text-text-muted">
            Loading members...
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
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => toggleMember(userId)}
                        >
                          Remove
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <p className="rounded-md border border-dashed border-border-default p-3 text-sm text-text-muted">
                No members yet.
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
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => toggleMember(person.user)}
                      >
                        Add
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-text-muted">No other members can join.</p>
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

      {error && <Alert tone="error">{error}</Alert>}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="submit"
          disabled={loading || availableRoles.length === 0}
          loading={loading}
        >
          {workflow ? "Save workflow" : "Create workflow"}
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            router.push(`/dashboard/teams/${team.id}/workflows`)
          }
        >
          <ArrowLeft className="h-4 w-4" />
          Cancel
        </Button>
      </div>

      <Dialog
        open={roleDialogOpen}
        onOpenChange={(next) => {
          if (!next && !creatingRole) {
            setRoleDialogOpen(false);
            setRoleDialogError("");
            setNewRoleName("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New approver role</DialogTitle>
            <DialogDescription>
              An existing name reuses that role.
            </DialogDescription>
          </DialogHeader>

          <Field label="Role name" htmlFor="new-role-name">
            <Input
              id="new-role-name"
              value={newRoleName}
              onChange={(event) => setNewRoleName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void createRole();
                }
              }}
              placeholder="e.g. Examinations Officer"
              autoFocus
              disabled={creatingRole}
            />
          </Field>

          {roleDialogError && <Alert tone="error">{roleDialogError}</Alert>}

          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setRoleDialogOpen(false);
                setRoleDialogError("");
                setNewRoleName("");
              }}
              disabled={creatingRole}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void createRole()}
              loading={creatingRole}
              disabled={!newRoleName.trim()}
            >
              Create role
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </form>
  );
}
