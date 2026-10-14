import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * `instrumentation-client.ts` patches `performance.measure` so React's RSC dev
 * instrumentation cannot crash the app when it reports an aborted component
 * (the upstream vercel/next.js#86060 bug). These tests load the module fresh
 * with a stub `measure` and assert the guard's two contracts: swallow only the
 * negative-timestamp failure, and install exactly once.
 */
const originalMeasure = window.performance.measure;

function setMeasure(value: unknown) {
  Object.defineProperty(window.performance, "measure", {
    configurable: true,
    writable: true,
    value,
  });
}

function clearGuard() {
  delete (window.performance as { __negativeMeasureGuard?: boolean })
    .__negativeMeasureGuard;
}

async function loadGuard() {
  vi.resetModules();
  await import("../instrumentation-client");
}

describe("instrumentation-client negative-timestamp guard", () => {
  beforeEach(() => {
    clearGuard();
  });

  afterEach(() => {
    clearGuard();
    setMeasure(originalMeasure);
    vi.restoreAllMocks();
  });

  it("swallows the negative-timestamp measurement React emits for aborted components", async () => {
    const throwing = vi.fn(() => {
      throw new DOMException(
        "Failed to execute 'measure' on 'Performance': 'ShimPage' cannot have a negative time stamp.",
        "InvalidAccessError",
      );
    });
    setMeasure(throwing);

    await loadGuard();

    expect(() =>
      window.performance.measure("ShimPage", { start: 10, end: -1 }),
    ).not.toThrow();
    expect(throwing).toHaveBeenCalledTimes(1);
  });

  it("rethrows any other measurement failure", async () => {
    setMeasure(
      vi.fn(() => {
        throw new Error("boom");
      }),
    );

    await loadGuard();

    expect(() => window.performance.measure("whatever")).toThrow("boom");
  });

  it("installs the patch only once across repeated evaluation", async () => {
    setMeasure(vi.fn());

    await loadGuard();
    const first = window.performance.measure;

    // A second top-level evaluation must not stack another wrapper.
    vi.resetModules();
    await import("../instrumentation-client");

    expect(window.performance.measure).toBe(first);
  });
});
