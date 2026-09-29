import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { EmployeeTable } from "@/components/hr/employee-table";
import type { Employee } from "@/lib/employees";

const activeEmployee: Employee = {
  id: 1,
  user_id: 7,
  email: "hod@test.luanar",
  first_name: "Test",
  last_name: "HOD",
  full_name: "Test HOD",
  role: "hod",
  designation: "Head of Department",
  department: "Bunda College",
  category: "academic",
  grade: "G",
  appointment_date: "2015-01-10",
  supervisor: null,
  is_active: true,
};

const inactiveEmployee: Employee = {
  ...activeEmployee,
  id: 2,
  email: "employee@test.luanar",
  first_name: "Test",
  last_name: "Employee",
  full_name: "Test Employee",
  role: "employee",
  designation: "Administrative Officer",
  department: "Administration",
  category: "administration",
  is_active: false,
};

describe("EmployeeTable", () => {
  it("renders employee rows with details", () => {
    render(<EmployeeTable employees={[activeEmployee]} />);

    expect(screen.getByText("Test HOD")).toBeInTheDocument();
    expect(screen.getByText("hod@test.luanar")).toBeInTheDocument();
    expect(screen.getByText("Bunda College")).toBeInTheDocument();
    expect(screen.getByText("Head of Department")).toBeInTheDocument();
    expect(screen.getByText("G")).toBeInTheDocument();
  });

  it("renders Active and Inactive badges for the right records", () => {
    render(<EmployeeTable employees={[activeEmployee, inactiveEmployee]} />);

    expect(screen.getByText("Test HOD")).toBeInTheDocument();
    expect(screen.getByText("Test Employee")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("links each row to the employee profile", () => {
    render(<EmployeeTable employees={[activeEmployee]} />);

    const link = screen.getByRole("link", { name: "Test HOD" });
    expect(link.getAttribute("href")).toBe("/dashboard/hr-admin/employees/1");
  });

  it("renders an empty state when there are no employees", () => {
    render(<EmployeeTable employees={[]} />);

    expect(screen.getByText("No employees found")).toBeInTheDocument();
  });
});