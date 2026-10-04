import { Suspense } from "react";

import { ApplicationsList } from "@/components/leave/ApplicationsList";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * `ApplicationsList` reads the open-application state from the query string via
 * `useSearchParams`, which Next.js requires to sit inside a Suspense boundary
 * so the page can still be prerendered.
 */
export default async function ApplicationsPage() {
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
        <ApplicationsList />
      </FadeIn>
    </Suspense>
  );
}
