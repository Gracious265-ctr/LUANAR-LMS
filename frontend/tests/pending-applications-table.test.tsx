import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

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

  it("renders an empty state when there are no pending applications", () => {
    render(<PendingApplicationsTable applications={[]} />);

    expect(screen.getByText("No pending applications")).toBeInTheDocument();
  });
});