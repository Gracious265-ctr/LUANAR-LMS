import { describe, expect, it, vi } from "vitest";

import {
  confirmBlock,
  createPlan,
  fetchApprovalsList,
  fetchCapabilities,
  fetchMyPlans,
  fetchPendingConfirmations,
  fetchPlanDetail,
  postPlanDecision,
  releaseBlock,
  submitPlan,
  updatePlanSettings,
} from "@/lib/plans/service";
import {
  makeApprovalList,
  makeCapabilities,
  makeMeta,
  makePendingConfirmations,
  makePlanDetail,
  makePlanRow,
} from "@/lib/plans/__fixtures__";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(
  impl: (url: string, init?: RequestInit) => Promise<Response>
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      impl(String(input), init)
    )
  );
}

describe("fetchMyPlans", () => {
  it("returns the list data for the requested scope", async () => {
    const row = makePlanRow();
    mockFetch((url) => {
      expect(url).toBe("/api/plans/?scope=team");
      return Promise.resolve(
        jsonResponse({ scope: "team", count: 1, results: [row] }, 200)
      );
    });
    const result = await fetchMyPlans("team");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.results[0].id).toBe(row.id);
  });

  it("uses the bare URL for the mine scope", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/");
      return Promise.resolve(
        jsonResponse({ scope: "mine", count: 0, results: [] }, 200)
      );
    });
    const result = await fetchMyPlans("mine");
    expect(result.ok).toBe(true);
  });

  it("surfaces 403 forbids", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ error: "No access" }, 403))
    );
    const result = await fetchMyPlans("department");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("forbidden");
      expect(result.message).toBe("No access");
    }
  });
});

describe("fetchPlanDetail", () => {
  it("returns the detail payload", async () => {
    const detail = makePlanDetail();
    mockFetch((url) => {
      expect(url).toBe("/api/plans/plan-1/");
      return Promise.resolve(jsonResponse(detail, 200));
    });
    const result = await fetchPlanDetail("plan-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.meta.id).toBe("plan-1");
  });

  it("maps 404 to not_found", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ error: "No" }, 404)));
    const result = await fetchPlanDetail("missing");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });
});

describe("createPlan", () => {
  it("posts the create payload", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body));
      expect(body.blocks).toHaveLength(1);
      return Promise.resolve(jsonResponse(makePlanDetail(), 201));
    });
    const result = await createPlan({
      period_start: "2026-07-01",
      period_end: "2027-06-30",
      blocks: [{ leave_type_id: 1, start_date: "2026-10-08", end_date: "2026-10-09" }],
    });
    expect(result.ok).toBe(true);
  });

  it("maps a 400 validation error", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ error: "Period invalid" }, 400))
    );
    const result = await createPlan({
      period_start: "2027-06-30",
      period_end: "2026-07-01",
      blocks: [{ leave_type_id: 1, start_date: "2026-10-08", end_date: "2026-10-09" }],
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.message).toBe("Period invalid");
    }
  });
});

describe("submitPlan", () => {
  it("returns the updated detail on success", async () => {
    const detail = makePlanDetail({
      meta: makeMeta({ status: "submitted", status_label: "Submitted" }),
      can_submit: false,
    });
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/plan-1/submit/");
      expect(init?.method).toBe("POST");
      return Promise.resolve(jsonResponse(detail, 200));
    });
    const result = await submitPlan("plan-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.meta.status).toBe("submitted");
  });

  it("surfaces validation errors and warnings from a 422", async () => {
    const detail = {
      errors: [{ field: "blocks", code: "overlap", message: "Overlaps another plan", block: "b1" }],
      warnings: ["Peer overlap detected"],
    };
    mockFetch(() => Promise.resolve(jsonResponse(detail, 422)));
    const result = await submitPlan("plan-1");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.errors).toHaveLength(1);
      expect(result.warnings).toEqual(["Peer overlap detected"]);
      expect(result.errors?.[0].code).toBe("overlap");
    }
  });

  it("maps a conflict on a non-draft plan", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ error: "Only a draft plan can be submitted." }, 409))
    );
    const result = await submitPlan("plan-1");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("conflict");
  });
});

describe("block actions", () => {
  it("confirmBlock posts to the confirm route", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/plan-1/blocks/block-1/confirm/");
      expect(init?.method).toBe("POST");
      return Promise.resolve(jsonResponse({ id: "block-1", status: "confirmed" }, 200));
    });
    const result = await confirmBlock("plan-1", "block-1");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.status).toBe("confirmed");
  });

  it("maps a state conflict on confirm", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ error: "Block cannot be confirmed now." }, 409))
    );
    const result = await confirmBlock("plan-1", "block-1");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("conflict");
  });

  it("releaseBlock posts to the release route", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/plan-1/blocks/block-1/release/");
      expect(init?.method).toBe("POST");
      return Promise.resolve(jsonResponse({ id: "block-1", status: "released" }, 200));
    });
    const result = await releaseBlock("plan-1", "block-1");
    expect(result.ok).toBe(true);
  });
});

describe("capabilities", () => {
  it("reads the capability counts", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/capabilities/");
      return Promise.resolve(jsonResponse(makeCapabilities(), 200));
    });
    const caps = await fetchCapabilities();
    expect(caps).toEqual(makeCapabilities());
  });

  it("defaults to zeroes when the call fails", async () => {
    mockFetch(() => Promise.reject(new Error("down")));
    const caps = await fetchCapabilities();
    expect(caps).toEqual({ is_approver: false, approver_pending_count: 0, pending_confirmation_count: 0 });
  });
});

describe("fetchPendingConfirmations", () => {
  it("returns the confirm queue", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/pending-confirmations/");
      return Promise.resolve(jsonResponse(makePendingConfirmations(), 200));
    });
    const result = await fetchPendingConfirmations();
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.count).toBe(1);
  });
});

describe("plan approvals list", () => {
  it("sends tab and page and returns rows", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/plans/approvals/?");
      expect(url).toContain("tab=pending");
      expect(url).toContain("page=2");
      return Promise.resolve(jsonResponse(makeApprovalList(), 200));
    });
    const result = await fetchApprovalsList("pending", 2);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.tab).toBe("pending");
  });
});

describe("postPlanDecision", () => {
  it("posts the decision and returns the fresh detail", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/approvals/plan-1/decision/");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body));
      expect(body.action).toBe("approve");
      expect(body.stage_version).toBe(1);
      return Promise.resolve(jsonResponse(makePlanDetail(), 200));
    });
    const result = await postPlanDecision("plan-1", { action: "approve", comment: "", stage_version: 1 });
    expect(result.ok).toBe(true);
  });

  it("maps a stage-changed conflict", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ error: "Already decided.", reason: "stage_changed" }, 409)
      )
    );
    const result = await postPlanDecision("plan-1", { action: "approve", stage_version: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("conflict");
      expect(result.reason).toBe("stage_changed");
    }
  });

  it("maps a 403 forbidden response with a reason", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ error: "Not your stage.", reason: "not_current_stage" }, 403)
      )
    );
    const result = await postPlanDecision("plan-1", { action: "approve", stage_version: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("forbidden");
      expect(result.reason).toBe("not_current_stage");
    }
  });
});

describe("updatePlanSettings", () => {
  it("patches the confirmation lead days", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/settings/");
      expect(init?.method).toBe("PATCH");
      const body = JSON.parse(String(init?.body));
      expect(body.confirmation_lead_days).toBe(21);
      return Promise.resolve(jsonResponse({ confirmation_lead_days: 21 }, 200));
    });
    const result = await updatePlanSettings(21);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.confirmation_lead_days).toBe(21);
  });
});