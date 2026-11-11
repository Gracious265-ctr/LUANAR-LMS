"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { assignEmployeeTeam } from "@/lib/employees-client";
import type { Employee } from "@/lib/employees";
import type { Team } from "@/lib/teams";
import { Button } from "@/components/ui/button";

/**
 * The people whose leave this team routes.
 *
 * Separate from the approval chain next to it: those are the approvers, these are
 * the submitters. An employee who is on a step of a chain here would be both, so
 * the two lists stay visibly distinct rather than sharing one roster.
 */
export function TeamRoster({
  team,
  members,
  candidates,
}: {
  team: Team;
  members: Employee[];
  candidates: Employee[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function change(employee: Employee, nextTeam: number | null) {
    setError("");
    setBusy(employee.id);
    try {
      await assignEmployeeTeam(employee.id, nextTeam);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  async function add() {
    if (selected === "") return;
    const employee = candidates.find((person) => person.id === Number(selected));
    if (!employee) return;
    await change(employee, team.id);
    setSelected("");
  }

  return (
    <div className="mt-3">
      {members.length === 0 ? (
        <p className="text-sm text-text-muted">
          Nobody&apos;s leave routes through this team yet. Add someone below.
        </p>
      ) : (
        <ul className="divide-y divide-border-default rounded-md border border-border-default">
          {members.map((member) => (
            <li
              key={member.id}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
            >
              <div>
                <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-text-primary">
                  {member.full_name}
                  {(team as any).manager_user === member.id && (
                    <span className="inline-flex items-center rounded-sm bg-brand-secondary-subtle px-2 py-0.5 text-[11px] font-semibold text-brand-secondary">
                      Manager
                    </span>
                  )}
                </p>
                <p className="text-xs text-text-muted">
                  {[member.designation, member.email].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void change(member, null)}
                disabled={busy === member.id}
                loading={busy === member.id}
                aria-label={`Remove ${member.full_name} from ${team.name}`}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="roster-candidate">
          Employee to add to this team
        </label>
        <select
          id="roster-candidate"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          disabled={candidates.length === 0}
          className="min-w-60 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">
            {candidates.length === 0
              ? "No employees without a team"
              : "Choose an employee..."}
          </option>
          {candidates.map((person) => (
            <option key={person.id} value={person.id}>
              {person.full_name}
              {person.designation ? ` — ${person.designation}` : ""}
            </option>
          ))}
        </select>
        <Button
          onClick={() => void add()}
          disabled={selected === "" || busy !== null}
        >
          Add to team
        </Button>
      </div>

      {error ? (
        <p className="mt-2 text-sm text-status-rejected">{error}</p>
      ) : null}

      <p className="mt-2 text-xs text-text-muted">Only employees without a team are offered here.</p>
    </div>
  );
}
