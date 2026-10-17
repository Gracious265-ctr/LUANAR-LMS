import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveReviewPanel } from "@/components/leave/LeaveReviewPanel";
import { LeaveReviewSummary } from "@/components/leave/leave-review-summary";
import { getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { SubmitError, submitApplication } from "@/lib/leave-validation";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import type { LeaveApplication } from "@/lib/leave-api";
import type { ValidationResult } from "@/lib/leave-validation";

// The panel reports completion through its callback, not a router: the old
// standalone page's navigation was the one thing the overlay replaced.
const { onSubmittedMock } = vi.hoisted(() => ({ onSubmittedMock: vi.fn() }));

vi.mock("@/lib/leave-api", () => ({ getLeaveApplication: vi.fn() }));
vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));
vi.mock("@/lib/leave-validation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-validation")>();
  return { ...actual, submitApplication: vi.fn() };
});
vi.mock("@/lib/hooks/useLeaveValidation", () => ({
  useLeaveValidation: vi.fn(),
}));

function makeApplication(over: Partial<LeaveApplication> = {}): LeaveApplication {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-09-28",
    end_date: "2026-10-02",
    calculated_days: 5,
    reason: "Attending a family wedding",
    status: "draft",
    reference_number: null,
    created_at: "2026-09-21T08:00:00Z",
    updated_at: "2026-09-21T08:00:00Z",
    submitted_at: null,
    working_days: null,
    calendar_days: null,
    financial_year_label: null,
    documents: [],
    ...over,
  };
}

function makeResult(over: Partial<ValidationResult> = {}): ValidationResult {
  return {
    valid: true,
    working_days: 5,
    calendar_days: 5,
    financial_year: "2026-27",
    available_balance: "24",
    balance_after_if_approved: "19",
    errors: [],
    warnings: [],
    skipped_checks: [],
    ...over,
  };
}

function renderReview(validation: Partial<ValidationResult>, app = makeApplication()) {
  vi.mocked(getLeaveApplication).mockResolvedValue(app);
  vi.mocked(getLeaveTypes).mockResolvedValue([
    { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    { id: 2, name: "Maternity Leave", requiresDocuments: true, maxDurationDays: 90 },
  ]);
  vi.mocked(useLeaveValidation).mockReturnValue({
    result: validation as ValidationResult,
    isLoading: false,
    error: null,
  });
  onSubmittedMock.mockClear();
  submitApplicationMockClear();
  return render(
    <LeaveReviewPanel applicationId="app-1" onSubmitted={onSubmittedMock} />
  );
}

function submitApplicationMockClear() {
  vi.mocked(submitApplication).mockClear();
}

describe("LeaveReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLeaveValidation).mockReturnValue({
      result: null,
      isLoading: false,
      error: null,
    });
  });

  it("shows the summary, working days, balance card and a green pass line", async () => {
    renderReview(makeResult());

    expect(await screen.findByText("Review your application")).toBeInTheDocument();
    expect(screen.getByText("2026-09-28 to 2026-10-02")).toBeInTheDocument();
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getByText(/All checks passed/)).toBeInTheDocument();
    expect(screen.getByText("Working days")).toBeInTheDocument();
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
    expect(screen.getByText("Available balance")).toBeInTheDocument();
    expect(
      screen.getByText(/Nothing is deducted until your application/i)
    ).toBeInTheDocument();
  });

  it("disables submission and renders backend issues when validation fails", async () => {
    renderReview(
      makeResult({
        valid: false,
        errors: [
          {
            code: "MIN_NOTICE_NOT_MET",
            field: "start_date",
            message: "Not enough notice given.",
          },
        ],
      })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Not enough notice given."
    );
    expect(screen.getByRole("button", { name: "Submit application" })).toBeDisabled();
  });

  it("does not render a balance card for leave without a deductible balance", async () => {
    renderReview(
      makeResult({ available_balance: null, balance_after_if_approved: null }),
      makeApplication({ leave_type_id: 2 })
    );

    expect(await screen.findByText("Review your application")).toBeInTheDocument();
    expect(screen.queryByText("Available balance")).not.toBeInTheDocument();
  });

  it("submits once on double-click and reports the submitted application", async () => {
    renderReview(makeResult());
    vi.mocked(submitApplication).mockResolvedValue({
      id: "app-1",
      reference_number: "LV-2026-27-000001",
      status: "submitted",
      submitted_at: "2026-09-21T10:00:00Z",
      working_days: 5,
      calendar_days: 5,
      leave_type: { id: 1 },
      start_date: "2026-09-28",
      end_date: "2026-10-02",
    });

    const button = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() =>
      expect(onSubmittedMock).toHaveBeenCalledWith("app-1")
    );
    expect(vi.mocked(submitApplication)).toHaveBeenCalledTimes(1);
  });

  it("replaces the panel issues and moves focus on a 422", async () => {
    renderReview(makeResult());
    vi.mocked(submitApplication).mockRejectedValue(
      new SubmitError(
        "Validation failed",
        422,
        {
          code: "VALIDATION_FAILED",
          errors: [
            {
              code: "OVERLAPPING_LEAVE",
              field: "start_date",
              message: "You already have a leave application in this period.",
            },
          ],
        }
      )
    );

    const button = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(button);

    expect(
      await screen.findByText("You already have a leave application in this period.")
    ).toBeInTheDocument();
    expect(onSubmittedMock).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(document.activeElement?.getAttribute("role")).toBe("alert")
    );
  });

  it("reports completion when the server reports ALREADY_SUBMITTED", async () => {
    renderReview(makeResult());
    vi.mocked(submitApplication).mockRejectedValue(
      new SubmitError("Already submitted", 409, {
        code: "ALREADY_SUBMITTED",
        reference_number: "LV-2026-27-000001",
      })
    );

    const button = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(button);

    await waitFor(() =>
      expect(onSubmittedMock).toHaveBeenCalledWith("app-1")
    );
  });

  it("shows a dismissible inline error for unexpected failures", async () => {
    renderReview(makeResult());
    vi.mocked(submitApplication).mockRejectedValue(
      new SubmitError("Server exploded", 500)
    );

    const button = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(button);

    expect(await screen.findByText("Server exploded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Server exploded")).not.toBeInTheDocument();
  });
});

describe("LeaveReviewSummary", () => {
  it("falls back to the stored calculated days when validation has no result", () => {
    render(
      <LeaveReviewSummary
        application={makeApplication({ calculated_days: 5 })}
        leaveTypeName="Annual Leave"
        validation={null}
      />
    );

    expect(screen.getByText("Working days")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("prefers the live validation count over the stored calculated days", () => {
    render(
      <LeaveReviewSummary
        application={makeApplication({ calculated_days: 5 })}
        leaveTypeName="Annual Leave"
        validation={makeResult({ working_days: 7, calendar_days: 8 })}
      />
    );

    expect(screen.getByText("Working days")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.queryByText("5")).not.toBeInTheDocument();
  });
});