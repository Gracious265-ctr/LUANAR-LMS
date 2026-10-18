"use client";

import { useState } from "react";

import type { LeaveType } from "@/lib/leave-config";
import {
  deactivateLeaveType,
  reactivateLeaveType,
} from "@/lib/leave-config-client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Confirm before deactivating (spec 3.4) — the second and third click of the
 * three-click budget, and the only place in the module where a decision is
 * consequential enough to deserve one.
 *
 * The same dialog reactivates: the copy and the verb follow the record's
 * current state rather than splitting into two components that differ by one
 * word.
 */
export function DeactivateDialog({
  leaveType,
  open,
  onOpenChange,
  onToggled,
}: {
  leaveType: LeaveType;
  open: boolean;
  /** Parent-owned so the dialog cannot outlive the record it acts on. */
  onOpenChange: (open: boolean) => void;
  /** Called with the updated record so the page can re-read its list. */
  onToggled: (leaveType: LeaveType) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const restoring = !leaveType.is_active;
  const verb = restoring ? "Reactivate" : "Deactivate";

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const updated = restoring
        ? await reactivateLeaveType(leaveType.id)
        : await deactivateLeaveType(leaveType.id);
      onToggled(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The change could not be saved."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) onOpenChange(false);
      }}
    >
      <DialogContent showCloseButton={!busy}>
        <div>
          <DialogTitle>
            {verb} {leaveType.name}?
          </DialogTitle>
          <DialogDescription className="mt-0.5">
            {restoring
              ? "Employees will be able to select this leave type again for new applications and plans."
              : "Employees will no longer be able to select this leave type for new applications or plans. Existing applications and plans are not affected."}
          </DialogDescription>
        </div>

        {error && <Alert tone="rejected">{error}</Alert>}

        <DialogFooter>
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={restoring ? "primary" : "destructive"}
            loading={busy}
            onClick={confirm}
          >
            {busy ? `${verb}ing…` : verb}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
