import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { PendingApplicationsTable } from "@/components/hr/pending-applications-table";
import type { PendingApplication } from "@/lib/reassignments";

const unassigned: PendingApplication = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual",
  start_date: "2026-10-01",
  end_date: "2026-10-05",
  calculated_days: 5,
  reason: "Family visit",
  submitted_at: "2026-09-18T10:00:00Z",
  current_approver: null,
  current_approver_name: "",
  acting_approver: null,
  acting_approver_name: "",
  is_delegated: false,
};

const delegated: PendingApplication = {
  ...unassigned,
  id: "app-2",
  reference_number: "LUANAR-2026-0002",
  current_approver: 3,
  current_approver_name: "Jane Dean",
  acting_approver: 5,
  acting_approver_name: "Bob HOD",
  is_delegated: true,
};

describe("PendingApplicationsTable", () => {
  it("renders reference, employee, leave type, dates, and approver", () => {
    render(
      <PendingApplicationsTable
        applications={[
          { ...unassigned, current_approver: 3, current_approver_name: "Jane Dean" },
        ]}
      />
    );

    expect(screen.getByText("LUANAR-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Annual")).toBeInTheDocument();
    expect(screen.getByText("2026-10-01 → 2026-10-05")).toBeInTheDocument();
    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
  });

  it("shows the acting delegate and who they cover for", () => {
    /* Reassigning to an approver who is away moves the spine but not the work,
       so the queue has to name both sides or the intervention reads as a no-op. */
    render(<PendingApplicationsTable applications={[delegated]} />);

    expect(screen.getByText("Bob HOD")).toBeInTheDocument();
    expect(screen.getByText("cover for Jane Dean")).toBeInTheDocument();
  });

  it("shows no acting-approver column value when nobody is covering", () => {
    render(
      <PendingApplicationsTable
        applications={[
          {
            ...unassigned,
            current_approver: 3,
            current_approver_name: "Jane Dean",
            acting_approver: 3,
            acting_approver_name: "Jane Dean",
          },
        ]}
      />
    );

    expect(screen.queryByText(/cover for/)).not.toBeInTheDocument();
  });

  it("shows Unassigned when there is no current approver", () => {
    render(<PendingApplicationsTable applications={[unassigned]} />);

    expect(screen.getByText("Unassigned")).toBeInTheDocument();
  });

  it("shows day count", () => {
    render(<PendingApplicationsTable applications={[unassigned]} />);

    expect(screen.getByText("(5d)")).toBeInTheDocument();
  });

  it("links each row to the reassign form with the application id", () => {
    render(<PendingApplicationsTable applications={[unassigned]} />);

    const link = screen.getByRole("link", { name: "Reassign" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/reassignments/new?application=app-1"
    );
  });

  it("turns the row action into a button that hands over the row record", () => {
    const onReassign = vi.fn();
    render(
      <PendingApplicationsTable
        applications={[unassigned, delegated]}
        onReassign={onReassign}
      />
    );

    // No link branch when a host owns the action: the overlay replaces the
    // navigation rather than doubling up with it.
    expect(screen.queryByRole("link")).toBeNull();

    // Named per row, because one bare "Reassign" per row is indistinguishable.
    fireEvent.click(screen.getByRole("button", { name: "Reassign LUANAR-2026-0001" }));
    expect(onReassign).toHaveBeenCalledWith(unassigned);

    fireEvent.click(screen.getByRole("button", { name: "Reassign LUANAR-2026-0002" }));
    expect(onReassign).toHaveBeenCalledWith(delegated);
  });

  it("renders an empty state when there are no pending applications", () => {
    render(<PendingApplicationsTable applications={[]} />);

    expect(screen.getByText("No pending applications")).toBeInTheDocument();
  });
});