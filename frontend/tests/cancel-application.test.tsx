import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CancelApplicationButton } from "@/components/cancellation/CancelApplicationButton";
import { ApiError } from "@/lib/approvals/service";

vi.mock("@/lib/cancellation/service", () => ({
  submitCancellation: vi.fn(),
}));

import { submitCancellation } from "@/lib/cancellation/service";
import type { CancellationEligibility } from "@/lib/cancellation/types";
import type { ApplicationSummary } from "@/lib/tracking/types";

const application = {
  id: "app-1",
  reference_number: "LV-2026-27-900001",
  leave_type: { id: 1, name: "Annual Leave" },
  start_date: "2026-12-07",
  end_date: "2026-12-18",
  working_days: 10,
} as Pick<
  ApplicationSummary,
  "id" | "reference_number" | "leave_type" | "start_date" | "end_date" | "working_days"
>;

function eligibility(
  overrides: Partial<CancellationEligibility> = {}
): Pick<CancellationEligibility, "cancellation_action" | "cancellation_blocked_reason" | "estimated_restoration_days"> {
  return {
    cancellation_action: "request",
    cancellation_blocked_reason: null,
    estimated_restoration_days: "5",
    ...overrides,
  };
}

const onSuccess = vi.fn();

function renderButton({
  action = "request",
  eligibilityOverrides = {},
}: {
  action?: "withdraw" | "request";
  eligibilityOverrides?: Partial<CancellationEligibility>;
} = {}) {
  return render(
    <CancelApplicationButton
      application={application}
      eligibility={eligibility({ cancellation_action: action, ...eligibilityOverrides })}
      onSuccess={onSuccess}
    />
  );
}

const REASON_PLACEHOLDER = "Explain why you are canceling this leave…";

function typeReason(dialog: ReturnType<typeof within>, value: string) {
  fireEvent.change(dialog.getByPlaceholderText(REASON_PLACEHOLDER), {
    target: { value },
  });
}

const openButtonName = (action: "withdraw" | "request") =>
  action === "withdraw" ? "Withdraw application" : "Request cancellation";

async function openDialog(action: "withdraw" | "request" = "request") {
  renderButton({ action });
  fireEvent.click(
    await screen.findByRole("button", { name: openButtonName(action) })
  );
  return within(await screen.findByRole("dialog"));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CancelApplicationButton · visibility", () => {
  it("renders 'Withdraw application' for the withdraw action", () => {
    renderButton({ action: "withdraw" });
    expect(
      screen.getByRole("button", { name: "Withdraw application" })
    ).toBeInTheDocument();
  });

  it("renders 'Request cancellation' for the request action", () => {
    renderButton({ action: "request" });
    expect(
      screen.getByRole("button", { name: "Request cancellation" })
    ).toBeInTheDocument();
  });

  it.each([
    ["leave_already_started", "Leave has already started."],
    ["not_cancellable_status", "This application cannot be cancelled in its current state."],
    ["open_request_exists", "A cancellation request is already pending."],
    ["no_cancellation_approvers", "No Supervisor or HOD approval chain exists for this application."],
  ] as const)(
    "hides the button and shows the muted reason for blocked code %s",
    (code, text) => {
      renderButton({
        eligibilityOverrides: {
          cancellation_action: null,
          cancellation_blocked_reason: code,
        },
      });
      expect(
        screen.queryByRole("button", { name: /withdraw|cancellation/i })
      ).not.toBeInTheDocument();
      expect(screen.getByText(text)).toBeInTheDocument();
    }
  );

  it("renders nothing when there is no action and no blocked reason", () => {
    const { container } = render(
      <CancelApplicationButton
        application={application}
        eligibility={eligibility({
          cancellation_action: null,
          cancellation_blocked_reason: null,
        })}
        onSuccess={onSuccess}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("CancelApplicationDialog · reason validation", () => {
  it("shows a live character counter and disables Continue below 10 chars", async () => {
    const dialog = await openDialog();
    expect(dialog.getByText("0/1000")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled();

    typeReason(dialog, "a".repeat(9));
    expect(dialog.getByText("9/1000")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("enables Continue at exactly 10 chars", async () => {
    const dialog = await openDialog();
    typeReason(dialog, "a".repeat(10));
    await waitFor(() => {
      expect(dialog.getByRole("button", { name: "Continue" })).toBeEnabled();
    });
  });

  it("counts characters after trimming whitespace", async () => {
    const dialog = await openDialog();
    typeReason(dialog, "   This reason is long enough   ");
    await waitFor(() => {
      expect(dialog.getByRole("button", { name: "Continue" })).toBeEnabled();
    });
  });

  it("rejects reasons over 1000 chars with an inline error", async () => {
    const dialog = await openDialog();
    typeReason(dialog, "a".repeat(1001));
    expect(dialog.getByText("1001/1000")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});

describe("CancelApplicationDialog · two-step flow", () => {
  it("shows the details recap and consequences on step 1", async () => {
    const dialog = await openDialog();
    expect(dialog.getByText("Annual Leave")).toBeInTheDocument();
    expect(dialog.getByText("7 Dec 2026 – 18 Dec 2026")).toBeInTheDocument();
    expect(
      dialog.getByText(
        "Your Supervisor/HOD must approve this. Your leave stays active until then."
      )
    ).toBeInTheDocument();
    expect(
      dialog.getByText(/will be restored to your FY balance if approved\./)
    ).toBeInTheDocument();
    expect(dialog.getByText("5")).toBeInTheDocument();
  });

  it("explains the immediate consequence for a withdrawal", async () => {
    const dialog = await openDialog("withdraw");
    expect(
      dialog.getByText("This application will be withdrawn immediately.")
    ).toBeInTheDocument();
  });

  it("Back preserves the typed reason and re-shows step 1", async () => {
    const dialog = await openDialog();
    const reason = "I will be away for the full period.";
    typeReason(dialog, reason);
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));

    expect(await dialog.findByText(reason)).toBeInTheDocument();
    expect(
      dialog.getByRole("button", { name: "Submit cancellation request" })
    ).toBeInTheDocument();

    fireEvent.click(dialog.getByRole("button", { name: "Back" }));
    const stepped = dialog.getByPlaceholderText(REASON_PLACEHOLDER);
    await waitFor(() => expect(stepped).toHaveValue(reason));
  });

  it("submits with the correct payload and calls onSuccess", async () => {
    vi.mocked(submitCancellation).mockResolvedValue({
      kind: "approved_leave",
      cancellation_request: { id: "req-1", status: "pending" },
    });
    const dialog = await openDialog();
    const reason = "I need to travel for family reasons.";
    typeReason(dialog, reason);
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      dialog.getByRole("button", { name: "Submit cancellation request" })
    );

    await waitFor(() => {
      expect(submitCancellation).toHaveBeenCalledWith("app-1", {
        reason,
        confirm: true,
        expected_action: "request",
      });
    });
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("prevents double submission while a request is in flight", async () => {
    vi.mocked(submitCancellation).mockReturnValue(new Promise(() => {}));
    const dialog = await openDialog();
    typeReason(dialog, "This is a well formed reason.");
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));

    const confirm = dialog.getByRole("button", {
      name: "Submit cancellation request",
    });
    fireEvent.click(confirm);
    await waitFor(() => expect(confirm).toBeDisabled());
    expect(submitCancellation).toHaveBeenCalledTimes(1);
  });

  it("maps action_changed to an inline message and a refetch", async () => {
    vi.mocked(submitCancellation).mockRejectedValueOnce(
      new ApiError(409, { code: "action_changed", detail: "State changed." })
    );
    const dialog = await openDialog();
    typeReason(dialog, "This is a well formed reason.");
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      dialog.getByRole("button", { name: "Submit cancellation request" })
    );

    expect(
      await dialog.findByText("The application changed since you opened this dialog.")
    ).toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("maps reason length errors from the server to the reason field", async () => {
    vi.mocked(submitCancellation).mockRejectedValueOnce(
      new ApiError(400, {
        code: "reason_too_short",
        detail: "The reason must be between 10 and 1000 characters.",
      })
    );
    const dialog = await openDialog();
    typeReason(dialog, "This is a well formed reason.");
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      dialog.getByRole("button", { name: "Submit cancellation request" })
    );

    expect(
      await dialog.findByText("The reason must be at least 10 characters.")
    ).toBeInTheDocument();
    // The server owns trimming; the dialog returns to step 1 with the error.
    expect(
      dialog.getByPlaceholderText(REASON_PLACEHOLDER)
    ).toBeInTheDocument();
  });
});

describe("CancelApplicationDialog · blocked reason echo", () => {
  it("surfaces open_request_exists as a block", async () => {
    vi.mocked(submitCancellation).mockRejectedValueOnce(
      new ApiError(409, { code: "open_request_exists", detail: "One open request." })
    );
    const dialog = await openDialog();
    typeReason(dialog, "This is a well formed reason.");
    fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      dialog.getByRole("button", { name: "Submit cancellation request" })
    );

    expect(
      await dialog.findByText("A cancellation request is already pending.")
    ).toBeInTheDocument();
  });
});