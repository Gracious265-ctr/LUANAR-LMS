import { Suspense } from "react";

import { ApplicationsList } from "@/components/leave/ApplicationsList";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * Drafts — in-progress applications, continued here (and from "New
 * Application", which resumes the most recently edited draft). "My
 * Applications" lives on `/dashboard/leave/applications`.
 *
 * `ApplicationsList` reads the open-application state from the query string via
 * `useSearchParams`, which Next.js requires to sit inside a Suspense boundary
 * so the page can still be prerendered.
 */
export default async function DraftsPage() {
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
        <ApplicationsList view="drafts" />
      </FadeIn>
    </Suspense>
  );
}
