"use client";

import { useRouter } from "next/navigation";

import { LeaveApplicationOverlay } from "./LeaveApplicationOverlay";

/**
 * The dedicated "New Application" surface.
 *
 * The sidebar's "New Application" item opens this route rather than the drafts
 * list, so the three destinations stay independent. The apply/review/submitted
 * journey is the shared overlay; here it is always open and does not mirror
 * itself into the query string, because this route has no list to come back to.
 * Closing (or finishing) returns to the full applications list.
 */
export function NewApplicationClient() {
  const router = useRouter();

  return (
    <LeaveApplicationOverlay
      open
      mode="create"
      syncUrl={false}
      onOpenChange={(open) => {
        // `replace`, not `push`: `/leave/new` is not a page the applicant
        // should step back into once the compose flow is dismissed. Landing on
        // the applications list is also the natural end of a submission.
        if (!open) router.replace("/leave");
      }}
    />
  );
}
