import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTracking } from "@/lib/tracking/service";
import type { TrackingResponse } from "@/lib/tracking/types";

const BASE_URL = "/api/leave/leave-applications/app-1/tracking/";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(impl: (url: string) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      return impl(url);
    })
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchTracking", () => {
  it("returns ok with the payload on 200", async () => {
    const payload = { status: "approved" } as unknown as TrackingResponse;
    mockFetch(() => Promise.resolve(jsonResponse(payload, 200)));

    const result = await fetchTracking("app-1");
    expect(result).toEqual({ ok: true, data: payload });
  });

  it("distinguishes 404 as not_found", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "The application does not exist." }, 404))
    );

    const result = await fetchTracking("app-1");
    expect(result).toEqual({ ok: false, kind: "not_found" });
  });

  it("distinguishes 409 application_not_submitted", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse(
          { code: "application_not_submitted", detail: "not submitted yet" },
          409
        )
      )
    );

    const result = await fetchTracking("app-1");
    expect(result).toEqual({ ok: false, kind: "not_submitted" });
  });

  it("treats other 409s as a generic error", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ code: "whocares" }, 409)));

    const result = await fetchTracking("app-1");
    expect(result).toEqual({
      ok: false,
      kind: "error",
      message: "The application cannot be tracked right now.",
    });
  });

  it("surfaces 5xx as an error and forwards the backend detail", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "Server exploded" }, 503))
    );

    const result = await fetchTracking("app-1");
    expect(result).toEqual({
      ok: false,
      kind: "error",
      message: "Server exploded",
    });
  });

  it("turns network failures into an error result", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));

    const result = await fetchTracking("app-1");
    expect(result).toMatchObject({ ok: false, kind: "error" });
  });

  it("requests the correct proxy path with credentials", async () => {
    const seen: string[] = [];
    mockFetch((url) => {
      seen.push(url);
      return Promise.resolve(jsonResponse({ status: "pending" }, 200));
    });
    await fetchTracking("app-1");
    expect(seen).toEqual([BASE_URL]);
  });
});