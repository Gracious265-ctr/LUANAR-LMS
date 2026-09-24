import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CancelApplicationDialog } from "@/components/cancellations/cancel-application-dialog";
import { makeEligibility } from "@/lib/cancellations/__fixtures__";
import type { CancellationAction } from "@/lib/cancellations/types";
import { submitCancellation } from "@/lib/cancellations/service";

vi.mock("@/lib/cancellations/service", () => ({
  submitCancellation: vi.fn(),
}));

const mockedSubmitCancellation = vi.mocked(submitCancellation);

const application = {
  id: "app-1",
  reference_number: "LV-2026-27-800123",
  leave_type: { id: 1, name: "Annual Leave" },
  start_date: "2026-12-07",
  end_date: "2026-12-18",
  working_days: 10,
  submitted_at: "2026-10-12T07:15:03Z",
};

function renderDialog(
  action: CancellationAction = "withdraw",
  overrides: {
    eligibility?: ReturnType<typeof makeEligibility>;
    onSubmitted?: () => void;
    onActionChanged?: () => void;
    onClose?: () => void;
  } = {}
) {
  const props = {
    action,
    eligibility: overrides.eligibility ?? makeEligibility(),
    application,
    onClose: overrides.onClose ?? vi.fn(),
    onSubmitted: overrides.onSubmitted ?? vi.fn(),
    onActionChanged: overrides.onActionChanged ?? vi.fn(),
  };
  const utils = render(<CancelApplicationDialog {...props} />);
  return { ...utils, props };
}

function goToConfirm() {
  fireEvent.change(screen.getByLabelText("Reason (required)"), {
    target: { value: "The university rescheduled my teaching block." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

describe("CancelApplicationDialog", () => {
  it("withdraw: submits the reason and confirm with the expected action", async () => {
    mockedSubmitCancellation.mockResolvedValue({
      ok: true,
      kind: "withdrawal",
      request: { id: "canc-1" } as never,
    });
    const onSubmitted = vi.fn();
    renderDialog("withdraw", { onSubmitted });

    goToConfirm();
    fireEvent.click(
      screen.getByRole("button", { name: "Yes, withdraw application" })
    );

    await waitFor(() => expect(mockedSubmitCancellation).toHaveBeenCalled());
    expect(mockedSubmitCancellation.mock.calls[0][0]).toBe("app-1");
    expect(mockedSubmitCancellation.mock.calls[0][1]).toEqual({
      reason: "The university rescheduled my teaching block.",
      confirm: true,
      expected_action: "withdraw",
    });
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("blocs a short reason and stays on step one", () => {
    renderDialog();
    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "Short" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      screen.getByText("The reason must be at least 10 characters.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  it("backs out of the confirmation step and edits the reason", async () => {
    mockedSubmitCancellation.mockResolvedValue({
      ok: true,
      kind: "approved_leave",
      request: { id: "canc-1" } as never,
    });
    renderDialog("request");

    goToConfirm();
    expect(
      screen.getByRole("button", { name: "Submit cancellation request" })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(
      screen.getByRole("button", { name: "Continue" })
    ).toBeInTheDocument();
  });

  it("shows the refresh path on an action_changed 409 with fresh eligibility", async () => {
    const fresh = makeEligibility({
      cancellation_action: "request",
      estimated_restoration_days: "10.0",
      restoration_financial_year: "2026-27",
    });
    mockedSubmitCancellation.mockResolvedValue({
      ok: false,
      kind: "error",
      code: "action_changed",
      message: "The application changed since you checked.",
      eligibility: fresh,
    });
    const onActionChanged = vi.fn();
    renderDialog("withdraw", { onActionChanged });

    goToConfirm();
    fireEvent.click(
      screen.getByRole("button", { name: "Yes, withdraw application" })
    );

    expect(
      await screen.findByText("The application changed since you checked.")
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh and review the latest state" })
    );
    expect(onActionChanged).toHaveBeenCalledWith(fresh);
  });

  it("shows a plain error message for other failures", async () => {
    mockedSubmitCancellation.mockResolvedValue({
      ok: false,
      kind: "error",
      code: "leave_already_started",
      message: "Leave has already started and cannot be cancelled.",
      eligibility: null,
    });
    renderDialog("withdraw");
    goToConfirm();
    fireEvent.click(
      screen.getByRole("button", { name: "Yes, withdraw application" })
    );
    expect(
      await screen.findByText("Leave has already started and cannot be cancelled.")
    ).toBeInTheDocument();
  });
});