import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ReassignmentTable } from "@/components/hr/reassignment-table";
import type { Reassignment } from "@/lib/reassignments";

const reassignment: Reassignment = {
  id: 1,
  application: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  from_approver: 3,
  from_approver_name: "Jane Dean",
  to_approver: 5,
  to_approver_name: "Bob HOD",
  reason: "Dean is on leave; reassigned to HOD cover.",
  decided_by: 1,
  decided_by_name: "Aisha HR",
  created_at: "2026-09-18T12:00:00Z",
};

describe("ReassignmentTable", () => {
  it("renders application, employee, from → to, reason, and decided by", () => {
    render(<ReassignmentTable reassignments={[reassignment]} />);

    expect(screen.getByText("LUANAR-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.getByText("Bob HOD")).toBeInTheDocument();
    expect(screen.getByText("Aisha HR")).toBeInTheDocument();
  });

  it("shows Unassigned when the previous approver is missing", () => {
    render(
      <ReassignmentTable
        reassignments={[
          { ...reassignment, from_approver: null, from_approver_name: "" },
        ]}
      />
    );

    expect(screen.getByText("Unassigned")).toBeInTheDocument();
  });

  it("renders an empty state when there are no reassignments", () => {
    render(<ReassignmentTable reassignments={[]} />);

    expect(screen.getByText("No reassignments yet")).toBeInTheDocument();
  });
});