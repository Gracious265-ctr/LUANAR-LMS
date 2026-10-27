"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { WorkflowRef } from "@/lib/teams";
import { routeTeamThrough } from "@/lib/teams-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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

  return (
    <>
      <span className="inline-flex items-center gap-2">
        {error && !confirming && (
          <span className="text-xs text-status-rejected">{error}</span>
        )}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setConfirming(true)}
        >
          Make default
        </Button>
      </span>

      <Dialog
        open={confirming}
        onOpenChange={(next) => {
          if (!next && !busy) {
            setConfirming(false);
            setError("");
          }
        }}
      >
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>
              Make &ldquo;{workflow.name}&rdquo; the default?
            </DialogTitle>
            <DialogDescription>
              This chain only starts routing once it is created with its steps
              and its members are enrolled. Everyone already enrolled keeps
              their chain — employees not on another chain will route through
              this one.
            </DialogDescription>
          </DialogHeader>

          {error && (
            <p className="text-sm text-status-rejected">{error}</p>
          )}

          <DialogFooter>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                setError("");
              }}
            >
              Keep the current default
            </Button>
            <Button
              disabled={busy}
              loading={busy}
              onClick={() => void routeThrough()}
            >
              Yes, make it default
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

