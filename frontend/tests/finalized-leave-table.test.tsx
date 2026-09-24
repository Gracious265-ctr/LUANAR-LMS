import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { FinalizedLeaveTable } from "@/components/hr/finalized-leave-table";
import type { FinalizedApplication } from "@/lib/audit";

const application: FinalizedApplication = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual",
  start_date: "2026-10-01",
  end_date: "2026-10-05",
  calculated_days: 5,
  reason: "Family visit",
  submitted_at: "2026-09-18T12:00:00Z",
  current_approver: 5,
  current_approver_name: "Bob HOD",
};

describe("FinalizedLeaveTable", () => {
  it("renders reference, employee, dates, and approver with a link", () => {
    render(<FinalizedLeaveTable applications={[application]} />);

    const link = screen.getByRole("link", { name: "LUANAR-2026-0001" });
    expect(link).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/audit/applications/app-1"
    );
    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Annual")).toBeInTheDocument();
    expect(screen.getByText("Bob HOD")).toBeInTheDocument();
    expect(screen.getByText("(5d)")).toBeInTheDocument();
  });

  it("shows Unassigned when there is no current approver", () => {
    render(
      <FinalizedLeaveTable
        applications={[
          { ...application, current_approver: null, current_approver_name: "" },
        ]}
      />
    );

    expect(screen.getByText("Unassigned")).toBeInTheDocument();
  });

  it("renders an empty state when there are no applications", () => {
    render(<FinalizedLeaveTable applications={[]} />);

    expect(screen.getByText("No finalized applications")).toBeInTheDocument();
  });
});