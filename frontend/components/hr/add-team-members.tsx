"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, UserPlus, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Alert, EmptyState } from "@/components/ui/states";
import type { Employee } from "@/lib/employees";
import { addTeamMembers } from "@/lib/team-members-client";

/**
 * The add-members page's body: search, choose, confirm.
 *
 * Two columns rather than an overlay, because choosing a roster is a decision
 * with its own shape: the list of who *may* join on the left, the people
 * actually chosen on the right, and one write at the end. Keeping the selection
 * visible while searching is why it is a page — a dialog that closes on save
 * hides the half of the decision that is still being made.
 *
 * The candidate list is the backend's answer, not a filter applied here: it
 * offers every unassigned employee of the team's category plus every unassigned
 * wide approver, whatever their category, because a wide holding crosses the
 * institution's halves. The same rule is re-checked on write, so this list can
 * only be an offer, never an authorisation.
 */
export function AddTeamMembers({
  team,
  candidates,
}: {
  team: { id: number; name: string; category: string };
  candidates: Employee[];
}) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return candidates;
    return candidates.filter((employee) =>
      [employee.full_name, employee.email, employee.designation].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [candidates, search]);

  const selectedPeople = useMemo(
    () =>
      selected
        .map((id) => candidates.find((employee) => employee.user_id === id))
        .filter((employee): employee is Employee => employee !== undefined),
    [candidates, selected]
  );

  function toggle(userId: number) {
    setSelected((current) =>
      current.includes(userId)
        ? current.filter((id) => id !== userId)
        : [...current, userId]
    );
  }

  function toggleAllShown() {
    const shown = filtered.map((employee) => employee.user_id);
    const everyShownSelected = shown.every((id) => selected.includes(id));
    setSelected((current) =>
      everyShownSelected
        ? current.filter((id) => !shown.includes(id))
        : Array.from(new Set([...current, ...shown]))
    );
  }

  async function submit() {
    if (selected.length === 0) return;
    setBusy(true);
    setError("");
    try {
      await addTeamMembers(team.id, selected);
      router.push(`/dashboard/teams/${team.id}?tab=members`);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Those employees could not be added."
      );
      setBusy(false);
    }
  }

  const teamHref = `/dashboard/teams/${team.id}?tab=members`;
  const everyShownSelected =
    filtered.length > 0 &&
    filtered.every((employee) => selected.includes(employee.user_id));

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <section className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              People who can join
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Unassigned employees of this team&apos;s category, plus unassigned
              wide approvers of either category. One employee belongs to one
              team.
            </p>
          </div>
          {filtered.length > 0 && (
            <Button type="button" variant="secondary" size="sm" onClick={toggleAllShown}>
              {everyShownSelected ? "Clear shown" : "Select all shown"}
            </Button>
          )}
        </div>

        <div className="relative mt-4">
          <label className="sr-only" htmlFor="candidate-search">
            Search people
          </label>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <Input
            id="candidate-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, email, or designation..."
            className="pl-9"
          />
        </div>

        {candidates.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="Nobody is available to add"
              description="Every matching employee is already on a team. Remove somebody from their current team first, or wait for a new employee record."
              titleAs="h4"
            />
          </div>
        ) : filtered.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="Nobody matches this search"
              description="Try a different name, or clear the search."
              titleAs="h4"
            />
          </div>
        ) : (
          <ul className="mt-4 max-h-[28rem] divide-y divide-border-default overflow-y-auto rounded-md border border-border-default">
            {filtered.map((employee) => {
              const isSelected = selected.includes(employee.user_id);
              const crossesCategory = employee.category !== team.category;
              return (
                <li key={employee.user_id}>
                  <label
                    htmlFor={`candidate-${employee.user_id}`}
                    className="flex cursor-pointer items-start gap-3 px-3 py-2 hover:bg-surface-hover"
                  >
                    <Checkbox
                      id={`candidate-${employee.user_id}`}
                      aria-label={employee.full_name}
                      checked={isSelected}
                      onCheckedChange={() => toggle(employee.user_id)}
                      className="mt-0.5"
                    />
                    <span className="min-w-0">
                      <span className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-text-primary">
                        {employee.full_name}
                        {crossesCategory && (
                          <Badge size="sm" tone="info">
                            Wide approver
                          </Badge>
                        )}
                      </span>
                      <span className="block text-xs text-text-muted">
                        {[employee.designation, employee.email]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <aside className="space-y-3 rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle lg:sticky lg:top-6">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Your selection</h3>
          <p className="mt-1 text-sm text-text-secondary">
            {selected.length === 0
              ? "Nobody chosen yet."
              : `${selected.length} ${
                  selected.length === 1 ? "person" : "people"
                } ready to add.`}
          </p>
        </div>

        {error && <Alert tone="error">{error}</Alert>}

        {selectedPeople.length > 0 && (
          <ul className="space-y-1.5">
            {selectedPeople.map((employee) => (
              <li
                key={employee.user_id}
                className="flex items-center justify-between gap-2 rounded-md border border-border-default px-2 py-1.5 text-sm"
              >
                <span className="min-w-0 truncate text-text-primary">
                  {employee.full_name}
                </span>
                <button
                  type="button"
                  onClick={() => toggle(employee.user_id)}
                  className="shrink-0 rounded p-1 text-text-muted hover:bg-surface-hover hover:text-text-primary"
                  aria-label={`Remove ${employee.full_name} from the selection`}
                >
                  <X className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <Button
          type="button"
          onClick={() => void submit()}
          disabled={busy || selected.length === 0}
          loading={busy}
          className="w-full"
        >
          <UserPlus className="h-4 w-4" />
          {selected.length <= 1
            ? "Add to team"
            : `Add ${selected.length} to team`}
        </Button>
        <Link
          href={teamHref}
          className={buttonVariants({ variant: "secondary", className: "w-full" })}
        >
          Cancel
        </Link>
      </aside>
    </div>
  );
}
