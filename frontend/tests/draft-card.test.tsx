import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DraftCard } from "@/components/leave/DraftCard";
import type { LeaveApplication } from "@/lib/leave-api";

vi.mock("@/lib/leave-api", () => ({
  deleteLeaveApplication: vi.fn(),
}));

import { deleteLeaveApplication } from "@/lib/leave-api";

const application: LeaveApplication = {
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
};

describe("DraftCard", () => {
  beforeEach(() => {
    vi.mocked(deleteLeaveApplication).mockReset();
    vi.mocked(deleteLeaveApplication).mockResolvedValue(undefined);
  });

  function openDeleteConfirm() {
    fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  }

  it("surfaces an error when deleting a draft fails", async () => {
    vi.mocked(deleteLeaveApplication).mockRejectedValueOnce(new Error("boom"));
    const onDelete = vi.fn();

    render(
      <DraftCard
        application={application}
        leaveTypeName="Annual"
        onDelete={onDelete}
      />
    );

    openDeleteConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    expect(
      await screen.findByText(/could not delete this draft/i)
    ).toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("removes the card after a successful delete", async () => {
    const onDelete = vi.fn();

    render(
      <DraftCard
        application={application}
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