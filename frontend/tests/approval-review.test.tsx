import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovalReview } from "@/components/approvals/approval-review";
import {
  ApiError,
  fetchApprovalDetail,
  submitDecision,
} from "@/lib/approvals/service";
import type { ApprovalDetail } from "@/lib/approvals/types";

vi.mock("@/lib/approvals/service", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approvals/service")>();
  return {
    ...actual,
    fetchApprovalDetail: vi.fn(),
    fetchCapabilities: vi.fn(),
    submitDecision: vi.fn(),
    fetchDocumentDownload: vi.fn(),
  };
});

const refreshMock = vi.fn();
vi.mock("@/lib/approvals/capabilities-context", () => ({
  useCapabilities: () => ({
    capabilities: { is_approver: true, pending_count: 1 },
    loading: false,
    refresh: refreshMock,
  }),
  CapabilitiesProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import detailDecided from "@/lib/approvals/__fixtures__/detail-decided.json";
import detailOpen from "@/lib/approvals/__fixtures__/detail.json";

const openFixture = detailOpen as unknown as ApprovalDetail;
const decidedFixture = detailDecided as unknown as ApprovalDetail;

beforeEach(() => {
  vi.clearAllMocks();
});

async function openDecisionDialog(name: "Approve" | "Reject") {
  const buttons = await screen.findAllByRole("button", { name });
  fireEvent.click(buttons[0]);
}

describe("ApprovalReview · rendering", () => {
  it("renders the reference, status, and application/employee sections", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValue(openFixture);
    render(<ApprovalReview applicationId="aa1" />);

    expect(await screen.findByText("LEA-2026-0041")).toBeInTheDocument();
    expect(screen.getByText("Pending Approval")).toBeInTheDocument();
    expect(screen.getAllByText("Miriam Banda").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Annual Leave").length).toBeGreaterThan(0);
    expect(screen.getByText("2 Nov 2026 – 6 Nov 2026")).toBeInTheDocument();
    expect(screen.getByText("Family visit.")).toBeInTheDocument();
    expect(screen.getByText("Approval history")).toBeInTheDocument();
    expect(screen.getByText("Leave history")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Leave balance")).toBeInTheDocument();
  });

  it("renders a read-only state once the stage is decided", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValue(decidedFixture);
    render(<ApprovalReview applicationId="aa1" />);

    expect((await screen.findAllByText("Approved")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Looks good.").length).toBeGreaterThan(0);
    expect(
      screen.getByText("No further action is required at your stage.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("shows a not-found state for missing applications", async () => {
    vi.mocked(fetchApprovalDetail).mockRejectedValue(new ApiError(404, {}));
    render(<ApprovalReview applicationId="missing" />);

    expect(await screen.findByText("Application not found")).toBeInTheDocument();
  });
});

describe("ApprovalReview · decisions", () => {
  it("approves with an optional comment and refreshes capabilities", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValue(openFixture);
    vi.mocked(submitDecision).mockResolvedValue(decidedFixture);
    render(<ApprovalReview applicationId="aa1" />);

    await openDecisionDialog("Approve");

    expect(
      await screen.findByRole("heading", { name: "Approve application" })
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Confirm approval" })
    );

    await waitFor(() => {
      expect(submitDecision).toHaveBeenCalledWith("aa1", {
        action: "approve",
        comment: "",
        stage_version: 3,
      });
    });

    expect(
      await screen.findByText(/Decision saved — you approved LEA-2026-0041/)
    ).toBeInTheDocument();
    expect(refreshMock).toHaveBeenCalled();
    expect(
      screen.queryByRole("heading", { name: "Approve application" })
    ).not.toBeInTheDocument();
  });

  it("requires a comment before rejecting", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValue(openFixture);
    vi.mocked(submitDecision).mockResolvedValue(decidedFixture);
    render(<ApprovalReview applicationId="aa1" />);

    await openDecisionDialog("Reject");

    const confirm = screen.getByRole("button", { name: "Reject application" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "Missing documents." },
    });
    expect(confirm).toBeEnabled();

    fireEvent.click(confirm);

    await waitFor(() => {
      expect(submitDecision).toHaveBeenCalledWith("aa1", {
        action: "reject",
        comment: "Missing documents.",
        stage_version: 3,
      });
    });
  });

  it("shows field errors from a 400 response", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValue(openFixture);
    vi.mocked(submitDecision).mockRejectedValue(
      new ApiError(400, { comment: ["This field is required."] })
    );
    render(<ApprovalReview applicationId="aa1" />);

    await openDecisionDialog("Reject");
    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject application" }));

    expect(
      await screen.findByText("This field is required.")
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reject application" })).toBeInTheDocument();
  });

  it("handles a stage conflict by offering to reload", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValueOnce(openFixture);
    vi.mocked(submitDecision).mockRejectedValue(new ApiError(409, {}));
    render(<ApprovalReview applicationId="aa1" />);

    await openDecisionDialog("Approve");
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));

    expect(
      await screen.findByText("This application has changed since you opened it. Reload to see the latest details before making a decision.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reload application" }));

    await waitFor(() => {
      expect(fetchApprovalDetail).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByRole("heading", { name: "Approve application" })
    ).not.toBeInTheDocument();
  });

  it("shows a read-only notice on 403 and refetches", async () => {
    vi.mocked(fetchApprovalDetail).mockResolvedValueOnce(openFixture);
    vi.mocked(submitDecision).mockRejectedValue(new ApiError(403, {}));
    render(<ApprovalReview applicationId="aa1" />);

    await openDecisionDialog("Approve");
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));

    expect(
      await screen.findByText("You can no longer decide on this application.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(fetchApprovalDetail).toHaveBeenCalledTimes(2);
    });
  });
});