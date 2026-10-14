import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationCard } from "@/components/leave/ApplicationCard";
import type { LeaveApplication } from "@/lib/leave-api";

vi.mock("@/lib/leave-api", () => ({
  deleteLeaveApplication: vi.fn(),
}));

import { deleteLeaveApplication } from "@/lib/leave-api";

function makeApplication(
  over: Partial<LeaveApplication> = {}
): LeaveApplication {
  return {
    id: "draft-1",
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

describe("ApplicationCard (draft)", () => {
  beforeEach(() => {
    vi.mocked(deleteLeaveApplication).mockReset();
    vi.mocked(deleteLeaveApplication).mockResolvedValue(undefined);
  });

  function openDeleteConfirm() {
    fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  }

  it("renders a Draft status pill", () => {
    render(
      <ApplicationCard
        application={makeApplication()}
        leaveTypeName="Annual"
        onDelete={vi.fn()}
      />
    );

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /edit/i })).toHaveAttribute(
      "href",
      "/dashboard/leave/draft-1/edit"
    );
  });

  it("rolls back the optimistic removal when deleting a draft fails", async () => {
    vi.mocked(deleteLeaveApplication).mockRejectedValueOnce(new Error("boom"));
    const onDelete = vi.fn();
    const onRestore = vi.fn();

    render(
      <ApplicationCard
        application={makeApplication()}
        leaveTypeName="Annual"
        onDelete={onDelete}
        onRestore={onRestore}
      />
    );

    openDeleteConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    // The host is asked to drop the row before the request settles (spec 3.5).
    expect(onDelete).toHaveBeenCalledWith("draft-1");
    expect(
      await screen.findByText(/could not delete this draft/i)
    ).toBeInTheDocument();
    // A failure tells the host to put the row back.
    expect(onRestore).toHaveBeenCalled();
  });

  it("removes the card after a successful delete", async () => {
    const onDelete = vi.fn();

    render(
      <ApplicationCard
        application={makeApplication()}
        leaveTypeName="Annual"
        onDelete={onDelete}
      />
    );

    openDeleteConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    await vi.waitFor(() => expect(onDelete).toHaveBeenCalledWith("draft-1"));
    expect(
      screen.queryByText(/could not delete this draft/i)
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationCard (non-draft)", () => {
  it("shows the reference number and a Track link for submitted", () => {
    render(
      <ApplicationCard
        application={makeApplication({
          id: "app-1",
          status: "submitted",
          reference_number: "LV-2026-27-000001",
          submitted_at: "2026-09-21T10:00:00Z",
        })}
        leaveTypeName="Annual"
        onDelete={vi.fn()}
      />
    );

    expect(screen.getByText("LV-2026-27-000001")).toBeInTheDocument();
    expect(screen.getByText("Pending Approval")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Track this application" })).toHaveAttribute(
      "href",
      "/applications/app-1"
    );
  });

  it("renders the correct pill and actions for each non-draft status", () => {
    const cases: Array<{ status: LeaveApplication["status"]; label: string }> = [
      { status: "approved", label: "Approved" },
      { status: "rejected", label: "Rejected" },
      { status: "correction_required", label: "Correction Required" },
      { status: "cancelled", label: "Cancelled" },
    ];

    for (const { status, label } of cases) {
      const { unmount } = render(
        <ApplicationCard
          application={makeApplication({ id: `app-${status}`, status })}
          leaveTypeName="Annual"
          onDelete={vi.fn()}
        />
      );

      expect(screen.getByText(label)).toBeInTheDocument();
      expect(
        screen.getAllByRole("link", { name: "Track this application" })
      ).toHaveLength(1);
      expect(screen.queryByRole("link", { name: /review/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Delete draft" })).not.toBeInTheDocument();
      unmount();
    }
  });
});