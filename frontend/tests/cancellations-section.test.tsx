import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CancellationSection } from "@/components/cancellations/cancellation-section";
import {
  makeApprovedRequest,
  makeEligibility,
  makeRejectedRequest,
} from "@/lib/cancellations/__fixtures__";
import type { CancellationHistoryResponse } from "@/lib/cancellations/types";
import type { CancellationHistoryResult } from "@/lib/cancellations/service";
import {
  fetchCancellationHistory,
  fetchEligibility,
  submitCancellation,
} from "@/lib/cancellations/service";
import { Toaster } from "@/components/ui/toast";

vi.mock("@/lib/cancellations/service", () => ({
  fetchEligibility: vi.fn(),
  fetchCancellationHistory: vi.fn(),
  submitCancellation: vi.fn(),
}));

const mockedFetchEligibility = vi.mocked(fetchEligibility);
const mockedFetchHistory = vi.mocked(fetchCancellationHistory);
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

function history(
  ...requests: ReturnType<typeof makeRejectedRequest>[]
): CancellationHistoryResult {
  return {
    ok: true,
    data: { count: requests.length, results: requests } satisfies CancellationHistoryResponse,
  };
}

function renderSection(onApplicationChanged: () => void = vi.fn()) {
  // Outcomes are reported through the global toast stack (spec 3.5).
  return render(
    <>
      <CancellationSection
        applicationId="app-1"
        application={application}
        onApplicationChanged={onApplicationChanged}
      />
      <Toaster />
    </>
  );
}

describe("CancellationSection", () => {
  it("shows the withdraw action and opens the dialog", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({ cancellation_action: "withdraw" }),
    });
    mockedFetchHistory.mockResolvedValue(history());
    renderSection();

    const button = await screen.findByRole("button", {
      name: /Withdraw application/,
    });
    fireEvent.click(button);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Reason (required)")).toBeInTheDocument();
  });

  it("submits through the dialog and reloads after success", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({ cancellation_action: "withdraw" }),
    });
    mockedFetchHistory.mockResolvedValue(history());
    mockedSubmitCancellation.mockResolvedValue({
      ok: true,
      kind: "withdrawal",
      request: { id: "canc-1" } as never,
    });
    const onApplicationChanged = vi.fn();
    renderSection(onApplicationChanged);

    fireEvent.click(
      await screen.findByRole("button", { name: /Withdraw application/ })
    );
    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "The university rescheduled my teaching block." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Yes, withdraw application" })
    );

    expect(await screen.findByText("Application withdrawn.")).toBeInTheDocument();
    expect(onApplicationChanged).toHaveBeenCalled();
    await waitFor(() =>
      expect(mockedFetchEligibility).toHaveBeenCalledTimes(2)
    );
  });

  it("shows the blocked reason when there is no action", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({
        cancellation_action: null,
        cancellation_blocked_reason: "open_request_exists",
      }),
    });
    mockedFetchHistory.mockResolvedValue(history());
    renderSection();

    expect(
      await screen.findByText(
        "A cancellation request is still awaiting approval."
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Withdraw application/ })
    ).not.toBeInTheDocument();
  });

  it("shows the request-action label for approved leave", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({
        cancellation_action: "request",
        estimated_restoration_days: "10.0",
        restoration_financial_year: "2026-27",
      }),
    });
    mockedFetchHistory.mockResolvedValue(history());
    renderSection();

    expect(
      await screen.findByRole("button", { name: /Request cancellation/ })
    ).toBeInTheDocument();
  });

  it("renders the card with the approval outcome banner", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({ cancellation_action: null }),
    });
    mockedFetchHistory.mockResolvedValue(history(makeApprovedRequest()));
    renderSection();

    expect(await screen.findByLabelText("Cancellation request")).toBeInTheDocument();
    expect(screen.getByText("Cancellation request")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Leave cancelled. 10 annual days restored to FY 2026-27 balance."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("collapses earlier rejected requests behind the history toggle", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: true,
      data: makeEligibility({ cancellation_action: null }),
    });
    mockedFetchHistory.mockResolvedValue(
      history(makeApprovedRequest({ id: "canc-2" }), makeRejectedRequest())
    );
    renderSection();

    const toggle = await screen.findByRole("button", {
      name: /Cancellation history \(1\)/,
    });
    expect(screen.getAllByText("Cancellation request")).toHaveLength(1);

    fireEvent.click(toggle);
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("renders nothing when there is no eligibility and no history", async () => {
    mockedFetchEligibility.mockResolvedValue({
      ok: false,
      kind: "not_found",
      message: "Application not found.",
    });
    mockedFetchHistory.mockResolvedValue({
      ok: false,
      kind: "error",
      message: "Failed to load cancellation history.",
    });
    const { container } = renderSection();
    await waitFor(() =>
      expect(mockedFetchEligibility).toHaveBeenCalled()
    );
    await waitFor(() => expect(container.innerHTML).toBe(""));
  });
});