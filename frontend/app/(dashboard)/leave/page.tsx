import { Suspense } from "react";

import { ApplicationsList } from "@/components/leave/ApplicationsList";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * "My Leave" — every application the applicant has submitted, across statuses,
 * except saved drafts (those live on `/leave/drafts` and nowhere else).
 *
 * The drafts-only view lives at `/leave/drafts`; the two are separate sidebar
 * destinations so neither lands on the other.
 */
export default async function MyLeavePage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-surface-muted" />
          ))}
        </div>
      }
    >
      <FadeIn>
        <ApplicationsList excludeStatus="draft" />
      </FadeIn>
    </Suspense>
  );
}
