"use client";

import { useState } from "react";
import { UserCheck } from "lucide-react";

import type { DelegateCandidate, Delegation } from "@/lib/delegations";
import { CoverRequestForm } from "@/components/approvals/cover-request-form";
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

export interface CoverRequestOverlayProps {
  open: boolean;
  candidates: DelegateCandidate[];
  onOpenChange: (open: boolean) => void;
  /** Called after a successful create so the host can refetch the list. */
  onSubmitted?: (delegation: Delegation) => void;
}

function periodLabel(delegation: Delegation): string {
  return delegation.ends_on
    ? `${delegation.starts_on} → ${delegation.ends_on}`
    : `From ${delegation.starts_on} (open-ended)`;
}

/**
 * Requests cover without leaving the page.
 *
 * The simplest shape of the overlay pattern: a cover request is a single POST
 * with no draft to autosave and no review step, so unlike the leave flow there
 * is one stage and no imperative handle to flush. The confirmation still renders
 * in place, which is the point — the new row appears in the table below
 * without the page ever navigating.
 */
export function CoverRequestOverlay(props: CoverRequestOverlayProps) {
  if (!props.open) return null;

  // The inner component owns `delegation` and only mounts while open, so
  // closing discards the confirmation and the next request starts on a blank
  // form. Keeping that state out of an effect also keeps the reset out of the
  // render that would otherwise flash the stale confirmation.
  return <CoverRequestOverlayInner key="cover-request" {...props} />;
}

function CoverRequestOverlayInner({
  candidates,
  onOpenChange,
  onSubmitted,
}: CoverRequestOverlayProps) {
  const [delegation, setDelegation] = useState<Delegation | null>(null);

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl"
        scrollable
        showCloseButton={!delegation}
      >
        {delegation ? (
          <>
            <DialogHeader>
              <DialogTitle>Cover requested</DialogTitle>
              <DialogDescription>
                HR will review your request before the cover takes effect.
              </DialogDescription>
            </DialogHeader>
            <Alert tone="approved" className="flex items-start gap-2">
              <UserCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>
                Your cover runs {periodLabel(delegation)}
                {delegation.delegate_name
                  ? `, with ${delegation.delegate_name} nominated to handle your approvals.`
                  : `. HR will assign a delegate.`}
              </span>
            </Alert>
            <DialogFooter>
              <Button
                variant="primary"
                onClick={() => {
                  onSubmitted?.(delegation);
                  onOpenChange(false);
                }}
              >
                Done
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Request cover</DialogTitle>
              <DialogDescription>
                Ask HR to route your pending approvals to someone else while you
                are away. You can nominate a delegate, or leave the choice to
                HR.
              </DialogDescription>
            </DialogHeader>
            <CoverRequestForm
              candidates={candidates}
              onSubmitted={setDelegation}
              onCancel={() => onOpenChange(false)}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
