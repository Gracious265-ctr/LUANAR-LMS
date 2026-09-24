import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CancellationDecisionPanel } from "@/components/cancellation/CancellationDecisionPanel";
import { ApiError } from "@/lib/approvals/service";
import {
  fetchCancellationApprovalDetail,
  submitCancellationDecision,
} from "@/lib/cancellation/service";
import type { CancellationApprovalDetail } from "@/lib/cancellation/types";

vi.mock("@/lib/cancellation/service", () => ({
  fetchCancellationApprovalDetail: vi.fn(),
  submitCancellationDecision: vi.fn(),
}));

function detail(
  overrides: Partial<CancellationApprovalDetail> = {}
): CancellationApprovalDetail {
  return {
    id: "req-1",
    kind: "approved_leave",
    status: "pending",
    reason: "I need to travel for family reasons.",
    requested_at: "2026-10-20T08:00:00Z",
    decided_at: null,
    stage_version: 1,
    balance_restored_days: "0",
    restored_financial_year: null,
    employee_notification_state: "pending",
    application_status_at_request: "approved",
    leave_started: false,
    can_act: true,
    my_decision: null,
    application: {
      id: "app-1",
      reference_number: "LV-2026-27-900004",
      leave_type: "Annual Leave",
      start_date: "2026-11-02",
      end_date: "2026-11-06",
      working_days: 5,
      status: "approved",
    },
    balance_impact: { restores_days: "5", financial_year: "2026-27" },
    stages: [
      {
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        approver_name: "Mr. Chikondi Banda",
        status: "pending",
        decided_at: null,
        comment: null,
      },
    ],
    ...overrides,
  };
}

const onRefetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

async function renderPanel(data: CancellationApprovalDetail) {
  vi.mocked(fetchCancellationApprovalDetail).mockResolvedValue(data);
  render(<CancellationDecisionPanel requestId="req-1" onRefetch={onRefetch} />);
  await screen.findByText("I need to travel for family reasons.");
}

async function openConfirmDialog(name: "Confirm approval" | "Confirm rejection") {
  fireEvent.click(screen.getByRole("button", { name: name === "Confirm approval" ? "Approve" : "Reject" }));
  return within(await screen.findByRole("dialog", { name }));
}

describe("CancellationDecisionPanel", () => {
  it("shows the reason, balance impact, stage tracker and decision buttons", async () => {
    await renderPanel(detail());

    expect(screen.getByText("I need to travel for family reasons.")).toBeInTheDocument();
    expect(
      screen.getByText("Approving restores 5 days to FY 2026-27")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Cancellation progress")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("approves with an optional comment and posts the right payload", async () => {
    vi.mocked(submitCancellationDecision).mockResolvedValue({
      application_status: "cancelled",
      balance_restored: true,
    });
    await renderPanel(detail());

    const dialog = await openConfirmDialog("Confirm approval");
    expect(
      dialog.getByText("This will cancel the leave and restore the deducted days.")
    ).toBeInTheDocument();

    const optional = dialog.getByPlaceholderText("Add an optional comment…");
    fireEvent.change(optional, { target: { value: "Coverage confirmed." } });

    fireEvent.click(dialog.getByRole("button", { name: "Yes, approve cancellation" }));
    await waitFor(() => {
      expect(submitCancellationDecision).toHaveBeenCalledWith("req-1", {
        decision: "approve",
        comment: "Coverage confirmed.",
        stage_version: 1,
      });
    });
    await waitFor(() => expect(onRefetch).toHaveBeenCalled());
  });

  it("requires a comment to reject, then posts it", async () => {
    vi.mocked(submitCancellationDecision).mockResolvedValue({
      application_status: "approved",
      balance_restored: false,
    });
    await renderPanel(detail());

    const dialog = await openConfirmDialog("Confirm rejection");
    const confirm = dialog.getByRole("button", { name: "Yes, reject cancellation" });
    fireEvent.click(confirm);

    expect(
      await dialog.findByText("A comment is required for rejections.")
    ).toBeInTheDocument();
    expect(submitCancellationDecision).not.toHaveBeenCalled();

    const textarea = dialog.getByLabelText("Comment");
    fireEvent.change(textarea, { target: { value: "Please re-apply later." } });
    fireEvent.click(confirm);

    await waitFor(() => {
      expect(submitCancellationDecision).toHaveBeenCalledWith("req-1", {
        decision: "reject",
        comment: "Please re-apply later.",
        stage_version: 1,
      });
    });
    await waitFor(() => expect(onRefetch).toHaveBeenCalled());
  });

  it("disables Approve and warns when the leave has started", async () => {
    await renderPanel(detail({ leave_started: true }));

    expect(
      screen.getByText("Leave has started; this request can only be rejected.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("shows a 409 toast, refetches the panel and the parent state", async () => {
    vi.mocked(submitCancellationDecision).mockRejectedValueOnce(
      new ApiError(409, { code: "request_not_pending", detail: "No longer pending." })
    );
    await renderPanel(detail());

    const dialog = await openConfirmDialog("Confirm approval");
    fireEvent.click(dialog.getByRole("button", { name: "Yes, approve cancellation" }));

    expect(
      await screen.findByText("This request changed. Refreshing…")
    ).toBeInTheDocument();
    await waitFor(() => expect(onRefetch).toHaveBeenCalled());
    // The panel re-fetched its own detail after the conflict.
    await waitFor(() => {
      expect(fetchCancellationApprovalDetail).toHaveBeenCalledTimes(2);
    });
  });

  it("shows the recorded decision when the request is no longer pending", async () => {
    await renderPanel(
      detail({
        status: "approved",
        decided_at: "2026-10-24T09:00:00Z",
        balance_restored_days: "5",
        restored_financial_year: "2026-27",
        can_act: false,
        my_decision: {
          action: "approved",
          role_label: "HOD",
          decided_at: "2026-10-24T09:00:00Z",
          comment: "",
        },
        stages: [
          {
            order: 1,
            role: "supervisor",
            role_label: "Supervisor",
            approver_name: "Mr. Chikondi Banda",
            status: "approved",
            decided_at: "2026-10-23T09:00:00Z",
            comment: "Coverage confirmed.",
          },
          {
            order: 2,
            role: "hod",
            role_label: "HOD",
            approver_name: "Dr. Grace Mwale",
            status: "approved",
            decided_at: "2026-10-24T09:00:00Z",
            comment: "",
          },
        ],
      })
    );

    expect(screen.getByText("You already decided on this request.")).toBeInTheDocument();
    expect(screen.getByText("Coverage confirmed.")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve|Reject/ })
    ).not.toBeInTheDocument();
  });

  it("flips to read-only after a 403 (not the current approver)", async () => {
    vi.mocked(submitCancellationDecision).mockRejectedValueOnce(
      new ApiError(403, {
        code: "not_current_approver",
        detail: "You are not the assigned approver for the current stage.",
      })
    );
    await renderPanel(detail());

    const dialog = await openConfirmDialog("Confirm approval");
    fireEvent.click(dialog.getByRole("button", { name: "Yes, approve cancellation" }));

    expect(
      await screen.findByText(/you are viewing this cancellation request in read-only mode/i)
    ).toBeInTheDocument();
  });

  it("shows read-only when it is not the viewer's turn (can_act = false)", async () => {
    await renderPanel(
      detail({
        can_act: false,
        stages: [
          {
            order: 1,
            role: "supervisor",
            role_label: "Supervisor",
            approver_name: "Mr. Chikondi Banda",
            status: "approved",
            decided_at: "2026-10-23T09:00:00Z",
            comment: null,
          },
          {
            order: 2,
            role: "hod",
            role_label: "HOD",
            approver_name: "Dr. Grace Mwale",
            status: "pending",
            decided_at: null,
            comment: null,
          },
        ],
      })
    );

    expect(
      screen.getByText(/you are viewing this cancellation request in read-only mode/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve|Reject/ })
    ).not.toBeInTheDocument();
  });
});