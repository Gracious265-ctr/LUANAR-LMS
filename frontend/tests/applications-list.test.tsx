import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationsList } from "@/components/leave/ApplicationsList";
import type { LeaveApplication } from "@/lib/leave-api";
import { getLeaveApplications } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";

vi.mock("@/lib/leave-api", () => ({
  getLeaveApplications: vi.fn(),
  deleteLeaveApplication: vi.fn(),
}));

vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));

import { deleteLeaveApplication } from "@/lib/leave-api";

function makeApplication(
  over: Partial<LeaveApplication> = {}
): LeaveApplication {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-10-01",
    end_date: "2026-10-05",
    calculated_days: 3,
    working_days: 3,
    calendar_days: 5,
    financial_year_label: "2026-27",
    reason: "Family visit",
    status: "draft",
    reference_number: null,
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    submitted_at: null,
    documents: [],
    ...over,
  };
}

describe("ApplicationsList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
  });

  it("fetches every application without a status filter", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 2,
      results: [
        makeApplication({
          id: "submitted-1",
          status: "submitted",
          reference_number: "LV-2026-27-000001",
          submitted_at: "2026-09-21T10:00:00Z",
        }),
        makeApplication({ id: "draft-1", status: "draft" }),
      ],
    });

    render(<ApplicationsList />);

    expect(await screen.findByText("My Applications")).toBeInTheDocument();
    expect(getLeaveApplications).toHaveBeenCalledWith(undefined);
    expect(screen.getByText("2 applications")).toBeInTheDocument();
    expect(screen.getByText("LV-2026-27-000001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Track this application" })).toHaveAttribute(
      "href",
      "/applications/submitted-1"
    );
    expect(screen.getByRole("button", { name: "Delete draft" })).toBeInTheDocument();
  });

  it("renders the empty state when there are no applications", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({ count: 0, results: [] });

    render(<ApplicationsList />);

    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
    expect(screen.getByText("0 applications")).toBeInTheDocument();
  });

  it("shows the error state and retries", async () => {
    vi.mocked(getLeaveApplications).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [makeApplication({ id: "submitted-1", status: "submitted" })],
    });

    render(<ApplicationsList />);

    const error = await screen.findByText("boom");
    expect(error).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByRole("link", { name: "Track this application" })).toBeInTheDocument();
  });

  it("refetches the list after a draft is deleted", async () => {
    vi.mocked(deleteLeaveApplication).mockResolvedValue(undefined);
    vi.mocked(getLeaveApplications)
      .mockResolvedValueOnce({
        count: 2,
        results: [
          makeApplication({ id: "submitted-1", status: "submitted" }),
          makeApplication({ id: "draft-1", status: "draft" }),
        ],
      })
      .mockResolvedValueOnce({
        count: 1,
        results: [makeApplication({ id: "submitted-1", status: "submitted" })],
      });

    render(<ApplicationsList />);

    const deleteButton = await screen.findByRole("button", { name: "Delete draft" });
    fireEvent.click(deleteButton);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    await vi.waitFor(() =>
      expect(getLeaveApplications).toHaveBeenCalledTimes(2)
    );
  });
});