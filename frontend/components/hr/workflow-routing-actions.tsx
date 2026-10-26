"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Team, WorkflowRef } from "@/lib/teams";
import { routeTeamThrough } from "@/lib/teams-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Make one of a team's chains its default, from wherever that chain is listed.
 *
 * A team routes every chain its people are enrolled on, all at once, so this
 * does not switch a live chain off: it sets the default fallback for employees
 * who are not enrolled on any chain, and the chain a wide approver uses when
 * they are looking at several of the team's chains at once. A chain only routes
 * applications after it is created with its steps and its members are enrolled;
 * a team member who is not in that chain never submits through it. That is why
 * it is a button with a confirmation sentence rather than a dropdown on the team
 * form — the person pressing it is changing a routing fallback for a group of
 * employees, not saving a row.
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
        Default
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
          This chain only starts routing once it is created with its steps and its members are enrolled. Everyone already enrolled keeps their chain — employees not on another chain will route through this one.
        </span>
        <Button
          size="sm"
          disabled={busy}
          loading={busy}
          onClick={() => void routeThrough()}
        >
          Yes, make it default
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => setConfirming(false)}
        >
          Keep the current default
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
        Make default
      </Button>
    </span>
  );
}

/**
 * The team's default chain, and the others it routes by enrolment.
 *
 * Every chain with steps is listed, one `RouteChainButton` per row: the team
 * routes all of them, and only one is the default.
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
        This team owns no chain with steps yet, so it routes nothing. Build the
        chain first.
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
