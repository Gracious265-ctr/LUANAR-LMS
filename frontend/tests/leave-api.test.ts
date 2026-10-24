import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deleteDocument,
  deleteLeaveApplication,
  listDocuments,
  updateLeaveApplication,
  uploadDocument,
} from "@/lib/leave-api";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function emptyResponse(status: number): Response {
  return new Response(null, { status });
}

function mockFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      impl(String(input), init)
    )
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("leave-api error seam", () => {
  it("surfaces a DRF detail sentence on a failed mutation", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "You already have this leave." }, 400))
    );

    await expect(
      updateLeaveApplication("app-1", { reason: "x" })
    ).rejects.toThrow("You already have this leave.");
  });

  it("surfaces the first field error when there is no detail", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ start_date: ["Start date is required."] }, 400))
    );

    await expect(updateLeaveApplication("app-1", {})).rejects.toThrow(
      "start_date: Start date is required."
    );
  });

  it("maps a code-keyed document error to its sentence", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ code: "document_not_active" }, 400)
      )
    );

    await expect(
      uploadDocument("app-1", new File(["x"], "x.pdf"))
    ).rejects.toThrow("This document has already been removed or replaced.");
  });

  it("falls back to the caller's message on an empty error body", async () => {
    mockFetch(() => Promise.resolve(emptyResponse(500)));

    await expect(listDocuments("app-1")).rejects.toThrow(
      "Failed to fetch documents"
    );
  });

  it("resolves a 204 DELETE without parsing a body", async () => {
    mockFetch(() => Promise.resolve(emptyResponse(204)));

    await expect(deleteLeaveApplication("app-1")).resolves.toBeUndefined();
    await expect(deleteDocument("app-1", "doc-1")).resolves.toBeUndefined();
  });
});
