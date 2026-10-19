"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { DelegateCandidate } from "@/lib/delegations";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { CoverRequestOverlay } from "@/components/approvals/CoverRequestOverlay";
import { Button } from "@/components/ui/button";

/** Query key for the cover-request overlay. */
export const COVER_PARAM = "cover";

/**
 * The "Request cover" affordance, with the form itself in an overlay.
 *
 * Mounted from both `CoverPanel` callers, which is why this has to be a client
 * component: `CoverPanel` is a server component and only receives data as
 * props, so the search-param read cannot live there.
 *
 * No `Suspense` boundary is needed around it even though it reads the query
 * string: every host resolves the current user through `cookies()`, so these
 * routes are never prerendered and there is no static shell to defer the client
 * component out of. If one of them ever becomes static, this needs wrapping,
 * the same way `/dashboard/leave/drafts` is.
 *
 * There is no old `new` route to redirect, because the form used to be
 * rendered inline and never had a URL of its own.
 */
export function CoverRequestSection({
  candidates,
}: {
  candidates: DelegateCandidate[];
}) {
  const router = useRouter();
  const overlay = useOverlayParam(COVER_PARAM);

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Request cover
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Going away? Ask HR to route your pending approvals to someone else.
            You can nominate a delegate, or leave the choice to HR.
          </p>
        </div>
        <Button variant="primary" onClick={overlay.openCreate} className="shrink-0">
          <Plus className="h-4 w-4" />
          Request cover
        </Button>
      </div>
      <CoverRequestOverlay
        open={overlay.isOpen}
        candidates={candidates}
        /*
          Refetch only. The overlay's Done handler calls `onSubmitted` and then
          `onOpenChange(false)`, so closing here as well would step back twice.
        */
        onSubmitted={() => router.refresh()}
        onOpenChange={(next) => {
          if (!next) overlay.close();
        }}
      />
    </>
  );
}
