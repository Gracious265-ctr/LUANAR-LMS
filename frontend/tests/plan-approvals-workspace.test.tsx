import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlansWorkspace } from "@/components/plans/plans-workspace";
import { PlanApprovalDetailView } from "@/components/plans/plan-approval-detail";
import {
  makeApprovalDetail,
  makeApprovalListItem,
  makeApprovalListResponse,
  makeListItem,
  makeListResponse,
  makePendingConfirmation,
} from "@/lib/plans/__fixtures__";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type Handler = (url: string, init?: RequestInit) => Promise<Response>;

function mockFetch(handler: Handler) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      handler(String(input), init)
    )
  );
}

/** Serves every plans endpoint the workspace and queue touch. */
function plansBackend(overrides: Record<string, Handler> = {}): Handler {
  return (url, init) => {
    for (const [fragment, handler] of Object.entries(overrides)) {
      if (url.includes(fragment)) return handler(url, init);
    }
    if (url.includes("/pending-confirmations/")) {
      return Promise.resolve(jsonResponse({ count: 0, results: [] }));
    }
    if (url.includes("/api/plans/approvals/")) {
      if (url.includes("/decision/")) {
        return Promise.resolve(jsonResponse(makeApprovalDetail()));
      }
      return Promise.resolve(jsonResponse(makeApprovalListResponse([makeApprovalListItem()])));
    }
    if (url.includes("/api/plans/?") || url.includes("/api/plans/admin/")) {
      return Promise.resolve(jsonResponse(makeListResponse([makeListItem()])));
    }
    if (url.includes("/api/plans/")) {
      return Promise.resolve(jsonResponse(makeApprovalDetail()));
    }
    return Promise.resolve(jsonResponse({}));
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("PlansWorkspace", () => {
  it("offers the four scopes, and hides 'All plans' from a non-HR caller", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace />);

    expect(await screen.findByRole("tab", { name: "My plans" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "My team" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "My department" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "All plans" })).not.toBeInTheDocument();
  });

  it("adds 'All plans' for HR", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace isHR />);

    expect(await screen.findByRole("tab", { name: "All plans" })).toBeInTheDocument();
  });

  it("offers the new plan route from every scope", async () => {
    render(<PlansWorkspace />);

    expect(screen.getByRole("link", { name: "New plan" })).toHaveAttribute(
      "href",
      "/dashboard/plans/new"
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "To confirm" }));

    // The header belongs to the workspace, so a scope change must not take the
    // only route to a new plan away.
    expect(screen.getByRole("link", { name: "New plan" })).toBeInTheDocument();
  });

  it("hides 'To decide' from a caller the server does not call an approver", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace />);

    await screen.findByRole("tab", { name: "My plans" });

    expect(screen.queryByRole("tab", { name: "To decide" })).not.toBeInTheDocument();
  });

  it("adds 'To decide' for an approver", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace isApprover />);

    expect(await screen.findByRole("tab", { name: "To decide" })).toBeInTheDocument();
  });

  it("stacks one scope switcher, never two", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace isApprover />);

    await screen.findByRole("tab", { name: "My plans" });

    // The workspace owns the scope, so the list below must not render its own.
    expect(
      screen.getAllByRole("tablist").filter((bar) =>
        within(bar).queryByRole("tab", { name: "My team" })
      )
    ).toHaveLength(1);
  });

  it("reads the scope it is showing", async () => {
    const seen: string[] = [];
    mockFetch(
      plansBackend({
        "/api/plans/": (url) => {
          seen.push(url);
          return Promise.resolve(jsonResponse(makeListResponse([makeListItem()])));
        },
      })
    );
    render(<PlansWorkspace />);

    await screen.findAllByRole("link", { name: /1 Oct – 18 Dec 2026/ });
    expect(seen.some((url) => url.includes("scope=mine"))).toBe(true);

    await userEvent.setup().click(screen.getByRole("tab", { name: "My team" }));

    await waitFor(() =>
      expect(seen.some((url) => url.includes("scope=team"))).toBe(true)
    );
  });

  it("shows the approver queue when that tab is chosen", async () => {
    mockFetch(plansBackend());
    render(<PlansWorkspace isApprover />);

    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));

    expect(
      await screen.findByRole("link", { name: "Chikondi Mbewe" })
    ).toHaveAttribute("href", "/dashboard/plans/approvals/plan-1");
  });

  it("shows the confirmations tab for everybody", async () => {
    mockFetch(
      plansBackend({
        "/pending-confirmations/": () =>
          Promise.resolve(
            jsonResponse({ count: 1, results: [makePendingConfirmation()] })
          ),
      })
    );
    render(<PlansWorkspace />);

    await userEvent.setup().click(await screen.findByRole("tab", { name: "To confirm" }));

    expect(
      await screen.findByRole("button", { name: "Confirm" })
    ).toBeInTheDocument();
  });
});

describe("approval queue", () => {
  async function renderQueue() {
    mockFetch(plansBackend());
    render(<PlansWorkspace isApprover />);
    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));
    await screen.findByRole("link", { name: "Chikondi Mbewe" });
  }

  it("names the pending count", async () => {
    mockFetch(
      plansBackend({
        "/api/plans/approvals/": () =>
          Promise.resolve(
            jsonResponse(makeApprovalListResponse([makeApprovalListItem()]))
          ),
      })
    );
    render(<PlansWorkspace isApprover />);
    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));

    expect(
      await screen.findByRole("tab", { name: /Awaiting my decision/ })
    ).toHaveTextContent("1");
  });

  it("says an empty queue is empty rather than loading forever", async () => {
    mockFetch(
      plansBackend({
        "/api/plans/approvals/": () =>
          Promise.resolve(jsonResponse(makeApprovalListResponse([])))
      })
    );
    render(<PlansWorkspace isApprover />);
    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));

    expect(
      await screen.findByText("No plans are waiting for you")
    ).toBeInTheDocument();
  });

  it("explains a queue the caller may not open", async () => {
    mockFetch(
      plansBackend({
        "/api/plans/approvals/": () => Promise.resolve(jsonResponse({}, 404)),
      })
    );
    render(<PlansWorkspace isApprover />);
    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));

    expect(
      await screen.findByText("You cannot review plans.")
    ).toBeInTheDocument();
  });

  it("switches to the decisions the caller already made", async () => {
    const seen: string[] = [];
    mockFetch(
      plansBackend({
        "/api/plans/approvals/": (url) => {
          seen.push(url);
          return Promise.resolve(makeApprovalListResponse([]) as unknown as Response);
        },
      })
    );
    render(<PlansWorkspace isApprover />);
    await userEvent.setup().click(await screen.findByRole("tab", { name: "To decide" }));
    await screen.findByRole("tab", { name: "Decided by me" });

    await userEvent.setup().click(screen.getByRole("tab", { name: "Decided by me" }));

    await waitFor(() =>
      expect(seen.some((url) => url.includes("tab=decided"))).toBe(true)
    );
  });

  it("links a row to the approver detail", async () => {
    await renderQueue();

    const link = await screen.findByRole("link", { name: "Chikondi Mbewe" });

    expect(link).toHaveAttribute("href", "/dashboard/plans/approvals/plan-1");
  });
});

describe("PlanApprovalDetailView", () => {
  function renderDetail(handler: Handler) {
    mockFetch(plansBackend({ "/api/plans/approvals/": handler }));
    return render(<PlanApprovalDetailView id="plan-1" />);
  }

  it("shows the plan and its approval chain", async () => {
    renderDetail(() => Promise.resolve(jsonResponse(makeApprovalDetail())));

    expect(
      await screen.findByRole("heading", { name: /1 Oct – 18 Dec 2026/ })
    ).toBeInTheDocument();
    expect(screen.getByTestId("plan-stage-chain")).toBeInTheDocument();
    expect(screen.getByText(/Chikondi Mbewe · Administration Team/)).toBeInTheDocument();
  });

  it("offers both decisions when the caller may act", async () => {
    renderDetail(() => Promise.resolve(jsonResponse(makeApprovalDetail())));

    expect(
      await screen.findByRole("button", { name: "Approve" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("names the reason instead of showing dead buttons", async () => {
    renderDetail(() =>
      Promise.resolve(jsonResponse(makeApprovalDetail({ can_decide: false })))
    );

    await screen.findByRole("heading", { name: /1 Oct/ });

    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText(/currently with the/)).toBeInTheDocument();
  });

  it("reports a decision the caller already made", async () => {
    renderDetail(() =>
      Promise.resolve(
        jsonResponse(
          makeApprovalDetail({
            can_decide: false,
            my_decision: {
              action: "approve",
              stage_order: 1,
              decided_at: "2026-09-22T10:00:00Z",
            },
          })
        )
      )
    );

    expect(await screen.findByText(/You approved this plan/)).toBeInTheDocument();
  });

  it("requires a reason to reject", async () => {
    renderDetail(() => Promise.resolve(jsonResponse(makeApprovalDetail())));

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));

    const dialog = await screen.findByRole("dialog", { name: "Reject plan" });
    const submit = within(dialog).getByRole("button", { name: "Reject" });

    expect(submit).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), {
      target: { value: "Too busy that week." },
    });

    expect(submit).toBeEnabled();
  });

  it("records the decision with the stage version it opened with", async () => {
    let sent: Record<string, unknown> | null = null;
    renderDetail((url, init) => {
      if (url.includes("/decision/")) {
        sent = JSON.parse(String(init?.body));
        return Promise.resolve(jsonResponse(makeApprovalDetail()));
      }
      return Promise.resolve(jsonResponse(makeApprovalDetail()));
    });

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog", { name: "Reject plan" });
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), {
      target: { value: "Too busy that week." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toEqual({
      action: "reject",
      comment: "Too busy that week.",
      stage_version: 1,
    });
  });

  it("offers a reload when somebody in the candidate set acted first", async () => {
    renderDetail((url) => {
      if (url.includes("/decision/")) {
        return Promise.resolve(jsonResponse({ detail: "Already decided." }, 409));
      }
      return Promise.resolve(jsonResponse(makeApprovalDetail()));
    });

    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve plan" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));

    expect(
      await within(dialog).findByText(/changed since you opened it/)
    ).toBeInTheDocument();
  });

  it("says a plan is not reviewable when the API says it is not", async () => {
    renderDetail(() => Promise.resolve(jsonResponse({}, 404)));

    expect(
      await screen.findByText("Plan not available")
    ).toBeInTheDocument();
  });
});
