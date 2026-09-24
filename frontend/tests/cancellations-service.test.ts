import { describe, expect, it, vi } from "vitest";

import {
  fetchCancellationDetail,
  fetchCancellationHistory,
  fetchCancellations,
  fetchEligibility,
  postCancellationDecision,
  submitCancellation,
} from "@/lib/cancellations/service";
import {
  makeDetail,
  makeEligibility,
  makeListResponse,
  makeRequest,
  makeRow,
} from "@/lib/cancellations/__fixtures__";

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

describe("fetchEligibility", () => {
  it("returns the eligibility payload", async () => {
    const eligibility = makeEligibility();
    mockFetch((url) => {
      expect(url).toBe("/api/leave/leave-applications/app-1/cancellation-eligibility/");
      return Promise.resolve(jsonResponse(eligibility, 200));
    });
    const result = await fetchEligibility("app-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.cancellation_action).toBe("withdraw");
  });

  it("maps 404 to not_found", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({}, 404)));
    const result = await fetchEligibility("missing");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });
});

describe("submitCancellation", () => {
  it("posts the payload with expected_action and returns kind + request", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/leave/leave-applications/app-1/cancel/");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body));
      expect(body.reason).toBe("Cover arranged");
      expect(body.confirm).toBe(true);
      expect(body.expected_action).toBe("withdraw");
      return Promise.resolve(
        jsonResponse({ kind: "withdrawal", request: makeRequest({ kind: "withdrawal" }) }, 200)
      );
    });
    const result = await submitCancellation("app-1", {
      reason: "Cover arranged",
      confirm: true,
      expected_action: "withdraw",
    });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.kind).toBe("withdrawal");
  });

  it("maps an action_changed 409 with fresh eligibility", async () => {
    const fresh = makeEligibility({ cancellation_action: "request", estimated_restoration_days: "10.0" });
    mockFetch(() =>
      Promise.resolve(
        jsonResponse(
          { code: "action_changed", detail: "The application changed since you checked.", eligibility: fresh },
          409
        )
      )
    );
    const result = await submitCancellation("app-1", {
      reason: "Cover arranged",
      confirm: true,
      expected_action: "withdraw",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("action_changed");
      expect(result.eligibility?.cancellation_action).toBe("request");
    }
  });

  it("maps a non-conflict error to a message", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ code: "not_cancellable_status", detail: "Cannot cancel." }, 409))
    );
    const result = await submitCancellation("app-1", {
      reason: "Cover arranged",
      confirm: true,
      expected_action: null,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toBe("Cannot cancel.");
  });
});

describe("fetchCancellationHistory", () => {
  it("returns the newest-first list", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/leave/leave-applications/app-1/cancellations/");
      return Promise.resolve(
        jsonResponse({ count: 1, results: [makeRequest()] }, 200)
      );
    });
    const result = await fetchCancellationHistory("app-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.results).toHaveLength(1);
  });
});

describe("fetchCancellations", () => {
  it("sends tab and page and returns the list", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/approvals/cancellations/?");
      expect(url).toContain("tab=decided");
      expect(url).toContain("page=2");
      return Promise.resolve(jsonResponse(makeListResponse([makeRow()]), 200));
    });
    const result = await fetchCancellations("decided", 2);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.results).toHaveLength(1);
  });
});

describe("fetchCancellationDetail", () => {
  it("returns the detail payload", async () => {
    const detail = makeDetail();
    mockFetch((url) => {
      expect(url).toBe("/api/approvals/cancellations/canc-1/");
      return Promise.resolve(jsonResponse(detail, 200));
    });
    const result = await fetchCancellationDetail("canc-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.requested_by_name).toBe("Chikondi Mbewe");
  });

  it("maps 404 to not_found", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ error: "Not viewable" }, 404)));
    const result = await fetchCancellationDetail("missing");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });
});

describe("postCancellationDecision", () => {
  it("sends the payload and returns the updated detail", async () => {
    const detail = makeDetail({ can_decide: false });
    mockFetch((url, init) => {
      expect(url).toBe("/api/approvals/cancellations/canc-1/decision/");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body));
      expect(body.decision).toBe("reject");
      expect(body.comment).toBe("Nope.");
      expect(body.stage_version).toBe(1);
      return Promise.resolve(jsonResponse(detail, 200));
    });
    const result = await postCancellationDecision("canc-1", {
      decision: "reject",
      comment: "Nope.",
      stage_version: 1,
    });
    expect(result.ok).toBe(true);
  });

  it("maps a stale-stage 409 to conflict", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ code: "stale_stage_version", error: "Changed." }, 409)
      )
    );
    const result = await postCancellationDecision("canc-1", {
      decision: "approve",
      comment: "",
      stage_version: 1,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("conflict");
      expect(result.code).toBe("stale_stage_version");
    }
  });

  it("maps comment_required 400 to a comment field error", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ code: "comment_required", error: "A comment is required when rejecting a cancellation." }, 400)
      )
    );
    const result = await postCancellationDecision("canc-1", {
      decision: "reject",
      comment: "",
      stage_version: 1,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.fields?.comment).toContain("required");
    }
  });
});