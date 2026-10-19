"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import type { Employee } from "@/lib/employees";
import type { TeamMemberSummary } from "@/lib/team-members";
import {
  addTeamMember,
  listTeamMembers,
  removeTeamMember,
} from "@/lib/team-members-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Input } from "@/components/ui/input";
import { Alert, EmptyState } from "@/components/ui/states";

const PAGE_SIZE = 10;

type RosterFilter = "all" | "approver" | "role" | "workflow" | "inactive";

/**
 * The roster of one team, managed.
 *
 * Who routes a team's applications: the people whose submissions its chains
 * decide. Compared with assignment-by-editing-the-employee, this screen reads
 * and writes the team's own roster, so a removal can be refused here by what
 * still ties the person to the team (a step appointment, a holding, a normal
 * workflow membership) rather than silently detaching the employee record.
 */
export function TeamMembersPanel({
  team,
  candidates,
}: {
  team: { id: number; name: string };
  candidates: Employee[];
}) {
  const router = useRouter();
  const [members, setMembers] = useState<TeamMemberSummary[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<RosterFilter>("all");
  const [page, setPage] = useState(1);
  const [selectedCandidate, setSelectedCandidate] = useState("");

  async function reload() {
    try {
      const rows = await listTeamMembers(team.id);
      setMembers(rows);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load the team's roster."
      );
    }
  }

  useEffect(() => {
    // Load the roster once for this team; the candidate list is static server
    // data, so only the team identity drives the refetch.
    listTeamMembers(team.id)
      .then((rows) => {
        setMembers(rows);
        setError("");
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Could not load the team's roster."
        );
      });
  }, [team.id]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (members ?? []).filter((member) => {
      if (filter === "approver" && !member.is_section_approver) return false;
      if (filter === "role" && !member.team_role) return false;
      if (filter === "workflow" && member.workflow_count === 0) return false;
      if (filter === "inactive" && member.is_active) return false;
      if (!query) return true;
      return [member.full_name, member.email, member.designation].some((value) =>
        value.toLowerCase().includes(query)
      );
    });
  }, [members, filter, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageRows = filtered.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE
  );

  function resetPage() {
    setPage(1);
  }

  async function addCandidate() {
    if (selectedCandidate === "") return;
    const userId = Number(selectedCandidate);
    setBusyId(userId);
    setError("");
    try {
      await addTeamMember(team.id, userId);
      setSelectedCandidate("");
      setPage(1);
      await reload();
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "That employee could not be added."
      );
    } finally {
      setBusyId(null);
    }
  }

  async function remove(member: TeamMemberSummary) {
    setBusyId(member.id);
    setError("");
    try {
      await removeTeamMember(team.id, member.user);
      await reload();
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "That employee could not be removed."
      );
    } finally {
      setBusyId(null);
    }
  }

  const count = members?.length ?? 0;

  return (
    <div className="space-y-3">
      {error && <Alert tone="error">{error}</Alert>}

      {members === null && !error ? (
        <p className="text-sm text-text-muted">Loading the roster...</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-52 flex-1">
              <label className="sr-only" htmlFor="roster-search">
                Search members
              </label>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <Input
                id="roster-search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  resetPage();
                }}
                placeholder="Search by name, email, or designation..."
                className="pl-9"
              />
            </div>
            <label className="sr-only" htmlFor="roster-filter">
              Filter members
            </label>
            <select
              id="roster-filter"
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value as RosterFilter);
                resetPage();
              }}
              className="rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            >
              <option value="all">All members</option>
              <option value="approver">Staff a step</option>
              <option value="role">Hold a team role</option>
              <option value="workflow">On a workflow</option>
              <option value="inactive">Inactive accounts</option>
            </select>
          </div>

          {count === 0 ? (
            <EmptyState
              title="No members yet"
              description="Nobody's leave routes through this team yet. Add someone below, and their submissions will follow the chain this team routes through."
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="No members match this search"
              description="Try a different name or clear the filter."
            />
          ) : (
            <ul className="divide-y divide-border-default rounded-md border border-border-default">
              {pageRows.map((member) => (
                <li
                  key={member.user}
                  className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-text-primary">
                      {member.full_name}
                      {!member.is_active && (
                        <Badge size="sm" tone="muted">
                          Inactive
                        </Badge>
                      )}
                      {member.is_section_approver && (
                        <Badge size="sm" tone="info">
                          Step approver
                        </Badge>
                      )}
                      {member.team_role && (
                        <Badge size="sm" tone="neutral">
                          {member.team_role}
                        </Badge>
                      )}
                    </p>
                    <p className="text-xs text-text-muted">
                      {[member.designation, member.email].filter(Boolean).join(" · ")}
                    </p>
                    {member.workflow_count > 0 && (
                      <p className="mt-0.5 text-xs text-text-secondary">
                        On{" "}
                        {member.workflow_memberships
                          .map(
                            (membership) => membership.workflow_name
                          )
                          .join(", ")}
                      </p>
                    )}
                  </div>
                  <ConfirmButton
                    size="sm"
                    onConfirm={() => remove(member)}
                    disabled={busyId === member.id}
                    loading={busyId === member.id}
                    prompt={`Remove ${member.full_name} from ${team.name}?`}
                    aria-label={`Remove ${member.full_name} from ${team.name}`}
                  >
                    Remove
                  </ConfirmButton>
                </li>
              ))}
            </ul>
          )}

          {pageCount > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <p className="text-xs text-text-muted">
                {filtered.length} member{filtered.length === 1 ? "" : "s"}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={safePage === 1}
                >
                  Previous
                </Button>
                <span className="px-2 text-xs text-text-muted">
                  Page {safePage} of {pageCount}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    setPage((current) => Math.min(pageCount, current + 1))
                  }
                  disabled={safePage === pageCount}
                >
                  Next
                </Button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="roster-candidate">
              Employee to add to this team
            </label>
            <select
              id="roster-candidate"
              value={selectedCandidate}
              onChange={(event) => setSelectedCandidate(event.target.value)}
              disabled={candidates.length === 0 || busyId !== null}
              className="min-w-60 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">
                {candidates.length === 0
                  ? "No employees to add to this team"
                  : "Choose an employee..."}
              </option>
              {candidates.map((person) => (
                <option key={person.id} value={person.user_id}>
                  {person.full_name}
                  {person.designation ? ` — ${person.designation}` : ""}
                </option>
              ))}
            </select>
            <Button
              onClick={() => void addCandidate()}
              disabled={selectedCandidate === "" || busyId !== null}
            >
              Add to team
            </Button>
          </div>

          <p className="text-xs text-text-muted">
            Only employees without a team who match this team&apos;s category are
            offered here, and never a wide approver — approvers are managed on
            the Approvers tab. Removing someone is refused while they still tie
            to this team — a step appointment, a team-wide role, an open
            approver period, or a place on one of its chains.
          </p>
        </>
      )}
    </div>
  );
}