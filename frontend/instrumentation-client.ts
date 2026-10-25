/**
 * Dev-only workaround for an upstream Next.js/React bug.
 *
 * React's server-component development instrumentation reports per-component
 * render timing via `performance.measure()`. When a component is rejected or
 * aborted before its children finish rendering — for example a route whose root
 * immediately calls `redirect()` (our `ShimPage` route shims) or `notFound()` —
 * React passes a `childrenEndTime` that was never updated from `-Infinity`, and
 * the browser rejects the measurement with an `InvalidAccessError`
 * ("... cannot have a negative time stamp").
 *
 * The fault is inside `react-server-dom-turbopack`, not our code — the redirect
 * shims are correct. Tracked upstream:
 *   - https://github.com/vercel/next.js/issues/86060 (open)
 *   - the Next.js-side fix (vercel/next.js#88688) was closed in favour of
 *     fixing it in React itself.
 *
 * It only reproduces under `next dev` with Turbopack and only pollutes the
 * console / dev overlay (no visual breakage, correct navigation), so we
 * swallow the offending measurement in development and leave production
 * untouched. This file runs after the document loads and before hydration, so
 * the patch is installed before any instrumentation can fire.
 */
if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
  const perf = window.performance as Performance & {
    __negativeMeasureGuard?: boolean;
  };

  // Guard against re-installing on Fast Refresh, which would wrap the wrapper
  // and stack try/catch blocks on every edit.
  if (!perf.__negativeMeasureGuard) {
    perf.__negativeMeasureGuard = true;

    const originalMeasure = perf.measure.bind(perf);

    perf.measure = ((
      ...args: Parameters<typeof originalMeasure>
    ): PerformanceMeasure => {
      try {
        return originalMeasure(...args);
      } catch (error) {
        // Only the negative-timestamp measurement is discarded; anything else
        // is a genuine problem and must still surface.
        const message =
          error && typeof error === "object" && "message" in error
            ? String((error as { message: unknown }).message)
            : "";
        const name =
          error && typeof error === "object" && "name" in error
            ? String((error as { name: unknown }).name)
            : "";

        if (
          message.includes("negative time stamp") ||
          name === "InvalidAccessError"
        ) {
          return undefined as unknown as PerformanceMeasure;
        }
        throw error;
      }
    }) as Performance["measure"];
  }
}

export {};
