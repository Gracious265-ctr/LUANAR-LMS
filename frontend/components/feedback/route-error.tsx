"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/ui/states";

/**
 * Shared fallback for a route segment's `error.tsx`. The thrown message is not
 * shown: in production Next replaces it with a generic string for server
 * errors, so the copy is fixed and the `digest` is surfaced instead, which is
 * what support needs to find the matching server log.
 */
export function RouteError({
  error,
  retry,
  title = "This section could not load",
}: {
  error: Error & { digest?: string };
  retry: () => void;
  title?: string;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <ErrorState
      title={title}
      message="Nothing was lost. Try again, and if it keeps failing, contact IT support with the reference below."
      onRetry={() => retry()}
    >
      {error.digest ? (
        <span className="mt-2 block font-mono text-xs text-text-muted">
          Reference: {error.digest}
        </span>
      ) : null}
    </ErrorState>
  );
}
