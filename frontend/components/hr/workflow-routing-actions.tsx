"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Team, WorkflowRef } from "@/lib/teams";
import { routeTeamThrough } from "@/lib/teams-client";

/**
 * Which of the team's chains new applications go through.
 *
 * Switching is a decision rather than an edit: the chain being left keeps its
 * steps, and the applications already inside it keep the chain they were
 * submitted against. That is why it is a button with a confirmation sentence
 * rather than a dropdown on the team form — the person pressing it is saying
 * which chain is live, not which row to save.
 */
export function WorkflowRoutingActions({
  team,
  workflows,
}: {
  team: Team;
  workflows: WorkflowRef[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState<number | null>(null);

  const routable = workflows.filter((workflow) => workflow.section_count > 0);

  if (routable.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        This team owns no chain with steps yet, so there is nothing it can
        route through. Build the chain first.
      </p>
    );
  }

  async function routeThrough(workflow: WorkflowRef) {
    setBusy(true);
    setError("");
    try {
      await routeTeamThrough(team.id, workflow.id);
      setConfirming(null);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-border-default">
        {routable.map((workflow) => (
          <li
            key={workflow.id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div>
              <span className="font-medium text-text-primary">
                {workflow.name}
              </span>
              <p className="text-xs text-text-muted">
                {workflow.section_count} step
                {workflow.section_count === 1 ? "" : "s"}
              </p>
            </div>
            {workflow.is_routing ? (
              <span className="inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary">
                Routing now
              </span>
            ) : confirming === workflow.id ? (
              <span className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-text-secondary">
                  New applications will go through this chain. Those already
                  inside the current one keep it.
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => routeThrough(workflow)}
                  className="rounded-md bg-button-primary px-2.5 py-1 font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? "Switching..." : "Yes, route through this"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setConfirming(null)}
                  className="rounded-md border border-border-default px-2.5 py-1 font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Keep the current chain
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(workflow.id)}
                className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-button-secondary-hover"
              >
                Route through this
              </button>
            )}
          </li>
        ))}
      </ul>
      {error && <p className="text-xs text-status-rejected">{error}</p>}
    </div>
  );
}
