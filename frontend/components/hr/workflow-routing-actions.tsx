"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Team, WorkflowRef } from "@/lib/teams";
import { routeTeamThrough } from "@/lib/teams-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Point a team at one chain, from wherever that chain is listed.
 *
 * Switching is a decision rather than an edit: the chain being left keeps its
 * steps, and the applications already inside it keep the chain they were
 * submitted against. That is why it is a button with a confirmation sentence
 * rather than a dropdown on the team form — the person pressing it is saying
 * which chain is live, not which row to save.
 *
 * Extracted from the list so the same control can sit on the team overview's
 * chain rows, which is what keeps "route this team through that chain" within
 * the three-click budget instead of hiding behind the Workflows page.
 */
export function RouteChainButton({
  teamId,
  workflow,
}: {
  teamId: number;
  workflow: WorkflowRef;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);

  if (workflow.is_routing) {
    return (
      <Badge size="sm" tone="info">
        Routing now
      </Badge>
    );
  }

  async function routeThrough() {
    setBusy(true);
    setError("");
    try {
      await routeTeamThrough(teamId, workflow.id);
      setConfirming(false);
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

  if (confirming) {
    return (
      <span className="flex flex-wrap items-center justify-end gap-2 text-xs">
        <span className="text-text-secondary">
          New applications will go through this chain. Those already inside the
          current one keep it.
        </span>
        <Button
          size="sm"
          disabled={busy}
          loading={busy}
          onClick={() => void routeThrough()}
        >
          Yes, route through this
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => setConfirming(false)}
        >
          Keep the current chain
        </Button>
        {error && <span className="text-xs text-status-rejected">{error}</span>}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2">
      {error && <span className="text-xs text-status-rejected">{error}</span>}
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setConfirming(true)}
      >
        Route through this
      </Button>
    </span>
  );
}

/**
 * Which of the team's chains new applications go through.
 *
 * The list of chains a team may route through, one `RouteChainButton` per row.
 */
export function WorkflowRoutingActions({
  team,
  workflows,
}: {
  team: Team;
  workflows: WorkflowRef[];
}) {
  const routable = workflows.filter((workflow) => workflow.section_count > 0);

  if (routable.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        This team owns no chain with steps yet, so there is nothing it can
        route through. Build the chain first.
      </p>
    );
  }

  return (
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
          <RouteChainButton teamId={team.id} workflow={workflow} />
        </li>
      ))}
    </ul>
  );
}
