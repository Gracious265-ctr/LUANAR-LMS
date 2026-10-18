"use client";

import { useState } from "react";

import { approveApprovals } from "@/lib/approvals/service";
import type { BulkApprovalItem, BulkApprovalResponse } from "@/lib/approvals/types";
import { Alert } from "@/components/ui/alert";
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

/** The word that has to be typed to confirm a batch approval. */
export const BULK_CONFIRM_WORD = "APPROVE";

/**
 * The confirmation gate in front of a batch approval.
 *
 * Approving many applications is one click with no per-row comment to slow it
 * down, so the pause is explicit: the approver types the word before the button
 * unlocks. The batch is approve-only and capped by the server, and every item is
 * still a separate audited decision, but the typed word is what keeps a
 * mis-click from sweeping a queue.
 */
export function BulkApproveDialog({
  open,
  items,
  onClose,
  onDone,
}: {
  open: boolean;
  items: BulkApprovalItem[];
  onClose: () => void;
  onDone: (result: BulkApprovalResponse) => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const count = items.length;
  const confirmed = confirmation.trim().toUpperCase() === BULK_CONFIRM_WORD;

  async function submit() {
    if (!confirmed || loading) return;
    setError("");
    setLoading(true);
    const result = await approveApprovals(items);
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setConfirmation("");
    onDone(result.data);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !loading) {
          setConfirmation("");
          setError("");
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Approve {count} application{count === 1 ? "" : "s"}?
          </DialogTitle>
          <DialogDescription>
            Each application is approved and audited separately, but there is no
            per-application comment and no undo. Type {BULK_CONFIRM_WORD} to
            confirm.
          </DialogDescription>
        </DialogHeader>

        <Field label="Type to confirm" htmlFor="bulk-confirm">
          <Input
            id="bulk-confirm"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={BULK_CONFIRM_WORD}
            autoComplete="off"
            disabled={loading}
          />
        </Field>

        {error && <Alert tone="rejected">{error}</Alert>}

        <DialogFooter>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setConfirmation("");
              setError("");
              onClose();
            }}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={submit}
            disabled={!confirmed}
            loading={loading}
          >
            {loading ? "Approving…" : `Approve ${count}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
