import { describe, expect, it, vi } from "vitest";

import {
  fetchApproval,
  fetchApprovals,
  fetchCapabilities,
  fetchDocumentDownload,
  postDecision,
} from "@/lib/approvals/service";
import { makeBriefing, makeListResponse, makeListItem, makeReview } from "@/lib/approvals/__fixtures__";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      impl(String(input), init)
    )
  );
}

describe("fetchApprovals", () => {
  it("returns the list data on success", async () => {
    const rows = [makeListItem()];
    mockFetch((url) => {
      expect(url).toContain("/api/approvals/?");
      expect(url).toContain("tab=pending");
      return Promise.resolve(jsonResponse(makeListResponse(rows), 200));
    });
    const result = await fetchApprovals("pending", "", 1);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.results).toHaveLength(1);
  });

  it("sends the tab, query and page parameters", async () => {
    mockFetch((url) => {
      expect(url).toContain("tab=decided");
      expect(url).toContain("q=Mbewe");
      expect(url).toContain("page=2");
      return Promise.resolve(jsonResponse(makeListResponse([]), 200));
    });
    const result = await fetchApprovals("decided", "Mbewe", 2);
    expect(result.ok).toBe(true);
  });

  it("returns an error result for a failing status", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ detail: "Boom" }, 500)));
    const result = await fetchApprovals("pending", "", 1);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toBe("Boom");
  });

  it("returns a network error on rejection", async () => {
    mockFetch(() => Promise.reject(new Error("down")));
    const result = await fetchApprovals("pending", "", 1);
    expect(result.ok).toBe(false);
  });
});

describe("fetchApproval", () => {
  it("returns the review payload", async () => {
    const review = makeReview();
    mockFetch((url) => {
      expect(url).toBe("/api/approvals/app-1/");
      return Promise.resolve(jsonResponse(review, 200));
    });
    const result = await fetchApproval("app-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.application.reference).toBe("LV-2026-000123");
  });

  it("maps 404 to not_found", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({}, 404)));
    const result = await fetchApproval("missing");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });
});

describe("postDecision", () => {
  it("sends the payload and returns the briefing", async () => {
    const briefing = makeBriefing();
    mockFetch((url, init) => {
      expect(url).toBe("/api/approvals/app-1/decision/");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body));
      expect(body.action).toBe("approve");
      expect(body.stage_version).toBe(1);
      return Promise.resolve(jsonResponse(briefing, 200));
    });
    const result = await postDecision("app-1", { action: "approve", comment: "", stage_version: 1 });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.status).toBe("approved");
  });

  it("maps 409 to conflict with the stage_changed reason", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ error: "Already decided", reason: "stage_changed" }, 409)
      )
    );
    const result = await postDecision("app-1", { action: "approve", comment: "", stage_version: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("conflict");
      expect(result.reason).toBe("stage_changed");
    }
  });

  it("maps 400 field errors", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ comment: ["This field may not be blank."] }, 400)
      )
    );
    const result = await postDecision("app-1", { action: "reject", comment: " ", stage_version: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.fields?.comment).toContain("blank");
    }
  });

  it("maps 403 with the reason code", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ error: "Not allowed", reason: "not_current_stage" }, 403)
      )
    );
    const result = await postDecision("app-1", { action: "approve", comment: "", stage_version: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("forbidden");
      expect(result.reason).toBe("not_current_stage");
    }
  });
});

describe("fetchCapabilities", () => {
  it("coerces string env values to booleans and numbers", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ is_approver: "true", pending_count: "5" }, 200)));
    const capabilities = await fetchCapabilities();
    expect(capabilities.is_approver).toBe(true);
    expect(capabilities.pending_count).toBe(5);
  });

  it("fails closed on network error", async () => {
    mockFetch(() => Promise.reject(new Error("down")));
    const capabilities = await fetchCapabilities();
    expect(capabilities).toEqual({ is_approver: false, pending_count: 0 });
  });
});

describe("fetchDocumentDownload", () => {
  it("returns the download url", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/approvals/app-1/documents/doc-1/download-url/");
      return Promise.resolve(
        jsonResponse({ id: "doc-1", name: "x.pdf", content_type: null, size: 1, download_url: "https://cdn/1", document_url: null }, 200)
      );
    });
    const doc = await fetchDocumentDownload("app-1", "doc-1");
    expect(doc.download_url).toBe("https://cdn/1");
  });
});