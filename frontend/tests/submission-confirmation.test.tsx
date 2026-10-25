import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  LeaveSubmissionResult,
  SubmittedClient,
} from "@/components/leave/LeaveSubmissionResult";
import { SubmissionConfirmation } from "@/components/leave/submission-confirmation";
import { getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import type { LeaveApplication } from "@/lib/leave-api";

const { replaceMock } = vi.hoisted(() => ({ replaceMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/leave-api", () => ({ getLeaveApplication: vi.fn() }));
vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));

function makeApplication(over: Partial<LeaveApplication> = {}): LeaveApplication {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-09-28",
    end_date: "2026-10-02",
    calculated_days: 5,
    reason: "Attending a family wedding",
    status: "submitted",
    reference_number: "LV-2026-27-000001",
    created_at: "2026-09-21T08:00:00Z",
    updated_at: "2026-09-21T10:00:00Z",
    submitted_at: "2026-09-21T10:00:00Z",
    working_days: 5,
    calendar_days: 5,
    financial_year_label: "2026-27",
    documents: [],
    ...over,
  };
}

describe("SubmissionConfirmation", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renders the reference number and copies it to the clipboard", async () => {
    render(
      <SubmissionConfirmation
        application={{
          id: "app-1",
          reference_number: "LV-2026-27-000001",
          status: "submitted",
          submitted_at: null,
          working_days: 5,
          calendar_days: null,
          leave_type: { id: 1 },
          start_date: "2026-09-28",
          end_date: "2026-10-02",
        }}
        leaveTypeName="Annual Leave"
      />
    );

    expect(screen.getByText("Application submitted")).toBeInTheDocument();
    expect(screen.getByText("LV-2026-27-000001")).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(screen.getByText(/5 working days/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Copy reference number" }));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("LV-2026-27-000001")
    );
    expect(screen.getByText("Copied")).toBeInTheDocument();
  });

  it("links back to the draft list and the dashboard", () => {
    render(
      <SubmissionConfirmation
        application={{
          id: "app-1",
          reference_number: "LV-2026-27-000001",
          status: "submitted",
          submitted_at: null,
          working_days: null,
          calendar_days: null,
          leave_type: { id: 1 },
          start_date: null,
          end_date: null,
        }}
      />
    );

    expect(
      screen.getByRole("link", { name: "View my applications" })
    ).toHaveAttribute("href", "/dashboard/leave/applications");
    expect(screen.getByRole("link", { name: "Back to dashboard" })).toHaveAttribute(
      "href",
      "/dashboard"
    );
  });
});

describe("SubmittedClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
    replaceMock.mockClear();
  });

  it("renders the confirmation for a submitted application", async () => {
    render(<SubmittedClient applicationId="app-1" />);

    expect(await screen.findByText("Application submitted")).toBeInTheDocument();
    expect(screen.getByText("LV-2026-27-000001")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirects back to the review screen when the application is not submitted", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(
      makeApplication({
        status: "draft",
        reference_number: null,
        submitted_at: null,
        working_days: null,
        calendar_days: null,
      })
    );

    render(<SubmittedClient applicationId="app-1" />);

    expect(
      await screen.findByText(/This application has not been submitted/)
    ).toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith("/dashboard/leave/app-1/review");
  });
});

describe("LeaveSubmissionResult", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
    replaceMock.mockClear();
  });

  it("shows the message in place instead of redirecting when the caller gives no handler", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(
      makeApplication({ status: "draft", reference_number: null })
    );

    // The dialog case: a redirect would tear down the overlay that is
    // displaying a legitimate result.
    render(<LeaveSubmissionResult applicationId="app-1" />);

    expect(
      await screen.findByText(/This application has not been submitted/)
    ).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
