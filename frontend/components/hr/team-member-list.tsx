"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";

import type { Employee } from "@/lib/employees";
import type { Team, TeamSection } from "@/lib/teams";
import {
  addSectionMember,
  listSectionMembers,
  removeSectionMember,
} from "@/lib/section-members-client";
import type { SectionMember } from "@/lib/workflows";

/**
 * Staffs one team's approval chain, one section at a time.
 *
 * A team no longer holds members itself — its workflow's sections do, so there
 * is exactly one place a person is recorded as able to act. Because sections
 * are shared, every team pointing at the same workflow sees the same roster.
 *
 * The chain is the team's workflow's, so the roster is read from the
 * section-members endpoint rather than flattened team rows: it can show who is
 * on a step and still say who is available at every other step.
 */
export function TeamMemberList({
  team,
  employees,
}: {
  team: Team;
  employees: Employee[];
}) {
  const router = useRouter();
  const [roster, setRoster] = useState<Record<number, SectionMember[]>>({});
  const [loadingRoster, setLoadingRoster] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"add" | number | null>(null);
  const [addingTo, setAddingTo] = useState<number | null>(null);

  const activeEmployees = employees.filter((employee) => employee.is_active);

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      team.sections.map(async (section) => {
        const members = await listSectionMembers(section.id);
        return [section.id, members] as const;
      })
    )
      .then((entries) => {
        if (cancelled) return;
        setRoster(Object.fromEntries(entries));
      })
      .catch(() => {
        if (cancelled) return;
        setError("Unable to load the section rosters. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoadingRoster(false);
      });
    return () => {
      cancelled = true;
    };
    // Refetch after a refresh re-drives the server props, so member counts and
    // rosters stay in step.
  }, [team.id, team.sections]);

  async function reloadSection(sectionId: number) {
    const members = await listSectionMembers(sectionId);
    setRoster((current) => ({ ...current, [sectionId]: members }));
  }

  async function add(event: React.FormEvent<HTMLFormElement>, section: TeamSection) {
    event.preventDefault();
    setError("");
    setBusy("add");

    const formData = new FormData(event.currentTarget);
    const user = String(formData.get("user") || "");

    if (!user) {
      setError("Choose a person to staff this section.");
      setBusy(null);
      return;
    }

    try {
      await addSectionMember(section.id, Number(user));
      setAddingTo(null);
      await reloadSection(section.id);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  async function remove(section: TeamSection, membership: SectionMember) {
    setError("");
    setBusy(membership.id);
    try {
      await removeSectionMember(membership.id);
      await reloadSection(section.id);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  if (team.sections.length === 0) {
    return (
      <p className="mt-3 text-sm text-text-muted">
        This team&apos;s workflow has no sections, so there is nobody to staff.
        Point the team at a workflow with approval sections first.
      </p>
    );
  }

  return (
    <div className="mt-3">
      {loadingRoster ? (
        <p className="text-sm text-text-muted">Loading section members…</p>
      ) : intersectionCnt(team, roster) === 0 ? (
        <p className="text-sm text-text-muted">
          Nobody is on this team&apos;s sections yet. An application routed
          here would have nobody to approve it.
        </p>
      ) : null}

      <div className="space-y-3">
        {team.sections.map((section) => {
          const members = roster[section.id] ?? [];
          const candidates = activeEmployees.filter(
            (employee) => !members.some((member) => member.user === employee.user_id)
          );
          return (
            <div
              key={section.id}
              role="group"
              aria-label={`Section ${section.order}: ${section.name}`}
              className="rounded-md border border-border-default bg-surface-card p-3"
            >
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="grid size-6 shrink-0 place-content-center rounded-full bg-brand-primary-subtle text-xs font-semibold text-brand-primary">
                  {section.order}
                </span>
                <span className="text-sm font-medium text-text-primary">
                  {section.approver_role_label}
                </span>
                <span className="text-xs text-text-muted">{section.name}</span>
                <span className="text-xs text-text-muted">
                  {section.member_count} member
                  {section.member_count === 1 ? "" : "s"}
                </span>
              </div>

              {members.length > 0 ? (
                <ul className="mt-2 space-y-1.5">
                  {members.map((member) => (
                    <li
                      key={member.id}
                      className="flex flex-wrap items-center gap-2 text-sm"
                    >
                      <span className="font-medium text-text-primary">
                        {member.user_name}
                      </span>
                      <span className="text-text-muted">{member.user_email}</span>
                      <button
                        type="button"
                        onClick={() => remove(section, member)}
                        disabled={busy === member.id}
                        aria-label={`Remove ${member.user_name} from ${section.name}`}
                        className="ml-auto rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busy === member.id ? "Removing..." : "Remove"}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-text-muted">
                  Nobody can act for this section yet.
                </p>
              )}

              {addingTo === section.id ? (
                <form
                  onSubmit={(event) => add(event, section)}
                  className="mt-2 flex flex-wrap items-center gap-2"
                >
                  <label className="sr-only" htmlFor={`add-${section.id}`}>
                    Add a member to {section.name}
                  </label>
                  <select
                    id={`add-${section.id}`}
                    name="user"
                    className="min-w-44 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
                  >
                    <option value="">Choose a person…</option>
                    {candidates.map((employee) => (
                      <option key={employee.user_id} value={employee.user_id}>
                        {employee.full_name || employee.email}
                      </option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={busy === "add"}
                    className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy === "add" ? "Adding..." : "Add"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddingTo(null)}
                    className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
                  >
                    Cancel
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={() => setAddingTo(section.id)}
                  disabled={candidates.length === 0}
                  className="mt-2 inline-flex items-center gap-1 rounded-md border border-border-default bg-button-secondary px-2.5 py-1 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add a member
                </button>
              )}
            </div>
          );
        })}
      </div>

      {error && <p className="mt-3 text-sm text-status-rejected">{error}</p>}

      <p className="mt-2 text-xs text-text-muted">
        Sections are shared: any other team on the same workflow sees the same
        people here, because there is just one place a person is recorded as
        able to act.
      </p>
    </div>
  );
}

/** How many distinct people sit on at least one of this team's sections. */
function intersectionCnt(team: Team, roster: Record<number, SectionMember[]>): number {
  const people = new Set<number>();
  for (const section of team.sections) {
    (roster[section.id] ?? []).forEach((member) => people.add(member.user));
  }
  return people.size;
}