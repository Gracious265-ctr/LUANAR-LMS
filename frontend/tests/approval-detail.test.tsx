import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalDetail } from "@/components/approvals/approval-detail";
import {
  makeApplicantExcludedReview,
  makeDecidedReview,
  makeReview,
  makeSkippedReview,
} from "@/lib/approvals/__fixtures__";
import { fetchApproval } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  fetchApproval: vi.fn(),
}));

const mockedFetchApproval = vi.mocked(fetchApproval);

describe("ApprovalDetail", () => {
  it("renders all review cards and the decision buttons", async () => {
    mockedFetchApproval.mockResolvedValue({ ok: true, data: makeReview() });
    render(<ApprovalDetail id="app-1" />);

    expect(await screen.findByText("LV-2026-000123", { selector: "h1" })).toBeInTheDocument();
    expect(screen.getByText("Application details")).toBeInTheDocument();
    expect(screen.getByText("Supporting documents")).toBeInTheDocument();
    expect(screen.getByText("Approval history")).toBeInTheDocument();
    expect(screen.getByText("Leave history")).toBeInTheDocument();
    expect(screen.getByText("Employee information")).toBeInTheDocument();
    expect(screen.getByText("Leave balance")).toBeInTheDocument();

    expect(screen.getAllByRole("button", { name: "Approve" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Reject" }).length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("button", { name: "Return for Correction" }).length
    ).toBeGreaterThan(0);
  });

  it("shows the timeline including awaiting and not-yet-reached stages", async () => {
    mockedFetchApproval.mockResolvedValue({ ok: true, data: makeReview() });
    render(<ApprovalDetail id="app-1" />);

    expect(await screen.findByText("Awaiting your decision")).toBeInTheDocument();
    expect(screen.getAllByText("Not yet reached")).toHaveLength(2);
    expect(screen.getByText("Looks good.")).toBeInTheDocument();
  });

  it("shows no skipped stage when the applicant shared a section", async () => {
    mockedFetchApproval.mockResolvedValue({
      ok: true,
      data: makeApplicantExcludedReview(),
    });
    render(<ApprovalDetail id="app-1" />);

    // The applicant is removed from the section's eligibility at submission and
    // a colleague on the same section decides it, so the chain runs straight
    // through with nothing bypassed.
    expect(await screen.findByText("Awaiting your decision")).toBeInTheDocument();
    expect(screen.queryByText(/Skipped/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Not yet reached")).toHaveLength(1);
  });

  it("shows a skipped stage with the reason it was passed over", async () => {
    mockedFetchApproval.mockResolvedValue({
      ok: true,
      data: makeSkippedReview(),
    });
    render(<ApprovalDetail id="app-1" />);

    // The applicant held the HOD stage, so it was skipped and the chain opened
    // at the Registrar. The stage stays in the history with its reason: a reader
    // must be able to tell a deliberate skip from a stage that was dropped.
    expect(await screen.findByText("Skipped")).toBeInTheDocument();
    expect(
      screen.getByText(/Applicant cannot approve their own application/)
    ).toBeInTheDocument();
    expect(screen.getAllByText("Not yet reached")).toHaveLength(1);
  });

  it("shows the read-only banner with an already_decided reason", async () => {
    mockedFetchApproval.mockResolvedValue({
      ok: true,
      data: makeDecidedReview(),
    });
    render(<ApprovalDetail id="app-1" />);

    expect(
      await screen.findByText(
        "You have already made a decision on this application."
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("shows the read-only banner with a self_application reason", async () => {
    mockedFetchApproval.mockResolvedValue({
      ok: true,
      data: makeReview({
        can_decide: false,
        decision_restriction: "self_application",
      }),
    });
    render(<ApprovalDetail id="app-1" />);

    expect(
      await screen.findByText("You cannot decide on your own application.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("shows the leave-history-unavailable note when scope is denied", async () => {
    const review = makeReview();
    review.history.leave_history.available = false;
    review.history.leave_history.entries = [];
    mockedFetchApproval.mockResolvedValue({ ok: true, data: review });
    render(<ApprovalDetail id="app-1" />);

    expect(
      await screen.findByText("Leave history is not available for your role.")
    ).toBeInTheDocument();
  });

  it("renders history rows for draft and submitted statuses without crashing", async () => {
    const review = makeReview();
    review.history.leave_history.entries = [
      ...review.history.leave_history.entries,
      {
        id: "draft-app",
        reference: "LV-2026-000999",
        leave_type: { id: 1, code: "annual", name: "Annual Leave" },
        start_date: "2026-09-01",
        end_date: "2026-09-03",
        working_days: 3,
        submitted_at: null,
        status: "draft",
      },
      {
        id: "submitted-app",
        reference: "LV-2026-000998",
        leave_type: { id: 1, code: "annual", name: "Annual Leave" },
        start_date: "2026-09-05",
        end_date: "2026-09-06",
        working_days: 2,
        submitted_at: "2026-08-20T09:00:00Z",
        status: "submitted",
      },
    ];
    mockedFetchApproval.mockResolvedValue({ ok: true, data: review });
    render(<ApprovalDetail id="app-1" />);

    expect(await screen.findByText("LV-2026-000999")).toBeInTheDocument();
    expect(screen.getByText("LV-2026-000998")).toBeInTheDocument();
    expect(screen.getAllByText("Draft")).toHaveLength(1);
  });

  it("renders the application-not-found state", async () => {
    mockedFetchApproval.mockResolvedValue({
      ok: false,
      kind: "not_found",
      message: "Application not found.",
    });
    render(<ApprovalDetail id="missing" />);
    expect(await screen.findByText("Application not found")).toBeInTheDocument();
  });
});