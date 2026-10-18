import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { EmployeeTable } from "@/components/hr/employee-table";
import { makeEmployee } from "@/lib/employees/__fixtures__";

const activeEmployee = makeEmployee({
  id: 1,
  user_id: 7,
  email: "lead@test.luanar",
  first_name: "Test",
  last_name: "Lead",
  full_name: "Test Lead",
  role: "approver",
  approver_roles: ["lead"],
  designation: "Team Leader",
  category: "academic",
  grade: "G",
  appointment_date: "2015-01-10",
  team: 4,
  team_name: "Bunda College Faculty",
  is_active: true,
});

const inactiveEmployee = makeEmployee({
  id: 2,
  user_id: 8,
  email: "employee@test.luanar",
  first_name: "Test",
  last_name: "Employee",
  full_name: "Test Employee",
  role: "employee",
  approver_roles: [],
  designation: "Administrative Officer",
  category: "administration",
  grade: "G",
  appointment_date: "2018-02-01",
  team: null,
  team_name: "",
  is_active: false,
});

describe("EmployeeTable", () => {
  it("renders employee rows with details", () => {
    render(<EmployeeTable employees={[activeEmployee]} />);

    expect(screen.getByText("Test Lead")).toBeInTheDocument();
    expect(screen.getByText("lead@test.luanar")).toBeInTheDocument();
    expect(screen.getByText("Team Leader")).toBeInTheDocument();
    expect(screen.getByText("G")).toBeInTheDocument();
    expect(screen.getByText("Bunda College Faculty")).toBeInTheDocument();
  });

  it("shows a dash for an employee on no team", () => {
    render(<EmployeeTable employees={[inactiveEmployee]} />);

    // Every other cell on this row is filled, so the lone dash is the team.
    expect(screen.getAllByText("—")).toHaveLength(1);
  });

  it("renders Active and Inactive badges for the right records", () => {
    render(<EmployeeTable employees={[activeEmployee, inactiveEmployee]} />);

    expect(screen.getByText("Test Lead")).toBeInTheDocument();
    expect(screen.getByText("Test Employee")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("links each row to the employee profile", () => {
    render(<EmployeeTable employees={[activeEmployee]} />);

    const link = screen.getByRole("link", { name: "Test Lead" });
    expect(link.getAttribute("href")).toBe("/hr-admin/employees/1");
  });

  it("renders an empty state when there are no employees", () => {
    render(<EmployeeTable employees={[]} />);

    expect(screen.getByText("No employees found")).toBeInTheDocument();
  });
});