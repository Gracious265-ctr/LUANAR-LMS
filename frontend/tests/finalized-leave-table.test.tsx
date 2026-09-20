import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { FinalizedLeaveTable } from "@/components/hr/finalized-leave-table";
import type { FinalizedApplication } from "@/lib/audit";

const app: FinalizedApplication = {
  id: 10,
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual Leave",
  start_date: "2026-10-05",
  end_date: "2026-10-09",
  calculated_days: 5,
  reason: "Family visit.",
  submitted_at: "2026-09-18T12:00:00Z",
  current_approver: 3,
  current_approver_name: "Jane Dean",
};

describe("FinalizedLeaveTable", () => {
  it("renders reference, employee, leave type, dates, approver, and submit date", () => {
    render(<FinalizedLeaveTable applications={[app]} />);

    expect(screen.getByText("LUANAR-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getByText("2026-10-05 → 2026-10-09")).toBeInTheDocument();
    expect(screen.getByText("(5d)")).toBeInTheDocument();
    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
  });

  it("links the reference to the application history page", () => {
    render(<FinalizedLeaveTable applications={[app]} />);

    const link = screen.getByRole("link", {
      name: "LUANAR-2026-0001",
    });
    expect(link).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/audit/applications/10"
    );
  });

  it("shows Unassigned when there is no current approver", () => {
    render(
      <FinalizedLeaveTable
        applications={[
          { ...app, current_approver: null, current_approver_name: "" },
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