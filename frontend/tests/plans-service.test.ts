import { describe, expect, it, vi } from "vitest";

import {
  confirmBlock,
  fetchAdminPlans,
  fetchPlan,
  fetchPlanApproval,
  fetchPlanApprovals,
  fetchPlans,
  fetchPendingConfirmations,
  fetchPlanSettings,
  postPlanDecision,
  releaseBlock,
  savePlanSettings,
  submitPlan,
} from "@/lib/plans/service";
import {
  makeApprovalDetail,
  makeApprovalListResponse,
  makeBlock,
  makeDetail,
  makeListResponse,
  makePendingConfirmation,
} from "@/lib/plans/__fixtures__";
import type { PlanValidationIssue } from "@/lib/plans/types";

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

describe("fetchPlans", () => {
  it("returns the list for the requested scope", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/plans/?");
      expect(url).toContain("scope=team");
      return Promise.resolve(jsonResponse(makeListResponse([]), 200));
    });

    const result = await fetchPlans("team");

    expect(result.ok).toBe(true);
  });

  it("reports a scope the caller is not placed in as forbidden", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "You have no team." }, 403))
    );

    const result = await fetchPlans("department");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("forbidden");
      expect(result.message).toBe("You have no team.");
    }
  });

  it("returns a network error on rejection", async () => {
    mockFetch(() => Promise.reject(new Error("down")));

    const result = await fetchPlans("mine");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("error");
  });
});

describe("fetchPlan", () => {
  it("encodes the id in the path", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/plan%2F1/");
      return Promise.resolve(jsonResponse(makeDetail(), 200));
    });

    const result = await fetchPlan("plan/1");

    expect(result.ok).toBe(true);
  });

  it("separates a missing plan from a failure", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({}, 404)));

    const result = await fetchPlan("plan-1");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });

  it("reports a plan the caller may not read as forbidden", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ detail: "Not yours." }, 403)));

    const result = await fetchPlan("plan-1");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("forbidden");
  });
});

describe("submitPlan", () => {
  it("posts and returns the submitted plan", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/plan-1/submit/");
      expect(init?.method).toBe("POST");
      return Promise.resolve(jsonResponse(makeDetail(), 200));
    });

    const result = await submitPlan("plan-1");

    expect(result.ok).toBe(true);
  });

  it("keeps the issues and warnings of a refused submission", async () => {
    const issues: PlanValidationIssue[] = [
      { field: "blocks", code: "insufficient_balance", message: "Too many days.", block: 0 },
    ];
    mockFetch(() =>
      Promise.resolve(
        jsonResponse(
          {
            detail: "This plan cannot be submitted yet.",
            errors: issues,
            warnings: [
              {
                peer_name: "A. Banda",
                peer_department: "Administration",
                leave_type_id: 1,
                start_date: "2026-10-12",
                end_date: "2026-10-13",
                overlaps_start: "2026-10-12",
                overlaps_end: "2026-10-13",
              },
            ],
          },
          422
        )
      )
    );

    const result = await submitPlan("plan-1");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.errors).toHaveLength(1);
      // A submission can be blocked and still carry a warning the owner has to
      // see, so warnings are never dropped alongside the errors.
      expect(result.warnings).toHaveLength(1);
    }
  });

  it("reports an already-submitted plan as a conflict", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({}, 409)));

    const result = await submitPlan("plan-1");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("conflict");
  });

  it("never throws when the body is not JSON", async () => {
    mockFetch(() =>
      Promise.resolve(new Response("<html>502</html>", { status: 422 }))
    );

    const result = await submitPlan("plan-1");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors).toEqual([]);
  });
});

describe("block actions", () => {
  it("confirms a block through the block-scoped path", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/plan-1/blocks/block-1/confirm/");
      expect(init?.method).toBe("POST");
      return Promise.resolve(jsonResponse({ status: "confirmed", id: "block-1" }, 200));
    });

    const result = await confirmBlock("plan-1", "block-1");

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.status).toBe("confirmed");
  });

  it("releases a block", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/plan-1/blocks/block-1/release/");
      return Promise.resolve(jsonResponse({ status: "released", id: "block-1" }, 200));
    });

    const result = await releaseBlock("plan-1", "block-1");

    expect(result.ok).toBe(true);
  });

  it("reports a block that can no longer change as a conflict", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "Too late." }, 409))
    );

    const result = await confirmBlock("plan-1", "block-1");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("conflict");
  });
});

describe("fetchPendingConfirmations", () => {
  it("returns the reserved blocks with their plan periods", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/pending-confirmations/");
      return Promise.resolve(
        jsonResponse({ count: 1, results: [makePendingConfirmation()] }, 200)
      );
    });

    const result = await fetchPendingConfirmations();

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.results[0].plan_id).toBe("plan-1");
  });
});

describe("approval queue", () => {
  it("sends the tab and page", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/plans/approvals/?");
      expect(url).toContain("tab=decided");
      expect(url).toContain("page=2");
      return Promise.resolve(jsonResponse(makeApprovalListResponse([]), 200));
    });

    const result = await fetchPlanApprovals("decided", 2);

    expect(result.ok).toBe(true);
  });

  it("treats a 404 from the queue as 'you cannot review plans'", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({}, 404)));

    const result = await fetchPlanApprovals("pending", 1);

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });

  it("reads the approver detail", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/approvals/plan-1/");
      return Promise.resolve(jsonResponse(makeApprovalDetail(), 200));
    });

    const result = await fetchPlanApproval("plan-1");

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.decision_version).toBe(1);
  });
});

describe("postPlanDecision", () => {
  it("sends the action, comment and stage version", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/approvals/plan-1/decision/");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({
        action: "reject",
        comment: "Too busy that week.",
        stage_version: 3,
      });
      return Promise.resolve(jsonResponse(makeDetail(), 200));
    });

    const result = await postPlanDecision("plan-1", {
      action: "reject",
      comment: "Too busy that week.",
      stage_version: 3,
    });

    expect(result.ok).toBe(true);
  });

  it("reports a stage somebody else already decided as a conflict", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ detail: "Already decided." }, 409))
    );

    const result = await postPlanDecision("plan-1", {
      action: "approve",
      comment: "",
      stage_version: 1,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("conflict");
  });

  it("pulls the comment error out of a 400 for the field", async () => {
    mockFetch(() =>
      Promise.resolve(jsonResponse({ comment: ["This field is required."] }, 400))
    );

    const result = await postPlanDecision("plan-1", {
      action: "reject",
      comment: "",
      stage_version: 1,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("validation");
      expect(result.fields?.comment).toBe("This field is required.");
    }
  });

  it("keeps the reason a decision was refused", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ detail: "Not your stage.", reason: "not_current_stage" }, 403)
      )
    );

    const result = await postPlanDecision("plan-1", {
      action: "approve",
      comment: "",
      stage_version: 1,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toBe("not_current_stage");
  });
});

describe("settings", () => {
  it("reads the confirmation window", async () => {
    mockFetch((url) => {
      expect(url).toBe("/api/plans/settings/");
      return Promise.resolve(jsonResponse({ confirmation_lead_days: 14 }, 200));
    });

    const result = await fetchPlanSettings();

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.confirmation_lead_days).toBe(14);
  });

  it("patches the confirmation window and returns what was saved", async () => {
    mockFetch((url, init) => {
      expect(url).toBe("/api/plans/settings/");
      expect(init?.method).toBe("PATCH");
      return Promise.resolve(jsonResponse({ confirmation_lead_days: 7 }, 200));
    });

    const result = await savePlanSettings({ confirmation_lead_days: 7 });

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.confirmation_lead_days).toBe(7);
  });
});

describe("fetchAdminPlans", () => {
  it("omits the filters that are not set", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/plans/admin/?");
      expect(url).toContain("page=1");
      expect(url).not.toContain("status=");
      expect(url).not.toContain("block_status=");
      return Promise.resolve(jsonResponse({ count: 0, next: null, previous: null, results: [] }, 200));
    });

    const result = await fetchAdminPlans({ page: 1 });

    expect(result.ok).toBe(true);
  });

  it("sends both filters when both are set", async () => {
    mockFetch((url) => {
      expect(url).toContain("status=approved");
      expect(url).toContain("block_status=reserved");
      return Promise.resolve(jsonResponse({ count: 0, next: null, previous: null, results: [] }, 200));
    });

    const result = await fetchAdminPlans({
      status: "approved",
      blockStatus: "reserved",
      page: 1,
    });

    expect(result.ok).toBe(true);
  });
});

describe("block payload handling", () => {
  it("survives a block list that is not an array", async () => {
    mockFetch(() =>
      Promise.resolve(
        jsonResponse({ ...makeDetail(), blocks: makeBlock() }, 200)
      )
    );

    const result = await fetchPlan("plan-1");

    // The cast is unchecked by design, so the read must not throw at runtime.
    expect(result.ok).toBe(true);
  });
});
