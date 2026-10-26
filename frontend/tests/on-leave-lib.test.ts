import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getOnLeave, onLeaveUrl } from "@/lib/on-leave";

vi.mock("@/lib/api-client", () => ({
  apiClient: vi.fn(),
  apiClientUrl: vi.fn(),
}));

import { apiClientUrl } from "@/lib/api-client";

const emptyPayload = {
  today: "2026-10-26",
  scope: { kind: "self", label: "Your leave", description: "" },
  counts: { on_leave: 0, upcoming: 0, returned: 0 },
  results: [],
};

describe("onLeaveUrl", () => {
  it("asks for the default view with no query string", () => {
    expect(onLeaveUrl()).toBe("/api/v1/leave/on-leave/");
  });

  it("sends the search term trimmed", () => {
    expect(onLeaveUrl({ q: "  Amina  " })).toBe(
      "/api/v1/leave/on-leave/?q=Amina"
    );
  });

  it("sends the past flag the backend accepts", () => {
    expect(onLeaveUrl({ includePast: true })).toBe(
      "/api/v1/leave/on-leave/?include_past=true"
    );
  });

  it("combines both filters", () => {
    expect(onLeaveUrl({ q: "a@b.test", includePast: true })).toBe(
      "/api/v1/leave/on-leave/?q=a%40b.test&include_past=true"
    );
  });

  it("omits a blank search rather than sending an empty filter", () => {
    expect(onLeaveUrl({ q: "   " })).toBe("/api/v1/leave/on-leave/");
  });
});

describe("getOnLeave", () => {
  beforeEach(() => {
    vi.mocked(apiClientUrl).mockResolvedValue(emptyPayload);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("reads the scoped endpoint", async () => {
    await getOnLeave();
    expect(apiClientUrl).toHaveBeenCalledWith("/api/v1/leave/on-leave/");
  });

  it("forwards the filters as a query string", async () => {
    await getOnLeave({ q: "Grace", includePast: true });
    expect(apiClientUrl).toHaveBeenCalledWith(
      "/api/v1/leave/on-leave/?q=Grace&include_past=true"
    );
  });

  it("returns the payload unchanged", async () => {
    await expect(getOnLeave()).resolves.toEqual(emptyPayload);
  });
});
