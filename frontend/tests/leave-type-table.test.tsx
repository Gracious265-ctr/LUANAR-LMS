import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { LeaveTypeTable } from "@/components/hr/leave-type-table";
import type { LeaveType } from "@/lib/leave-rules";

const annual: LeaveType = { id: 1, name: "Annual leave", code: "annual" };
const maternity: LeaveType = { id: 2, name: "Maternity leave", code: "maternity" };

describe("LeaveTypeTable", () => {
  it("renders leave type rows with details", () => {
    render(<LeaveTypeTable leaveTypes={[annual]} />);

    expect(screen.getByText("Annual leave")).toBeInTheDocument();
    expect(screen.getByText("annual")).toBeInTheDocument();
  });

  it("renders multiple leave types", () => {
    render(<LeaveTypeTable leaveTypes={[annual, maternity]} />);

    expect(screen.getByText("Annual leave")).toBeInTheDocument();
    expect(screen.getByText("Maternity leave")).toBeInTheDocument();
    expect(screen.getByText("maternity")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<LeaveTypeTable leaveTypes={[maternity]} />);

    const link = screen.getByRole("link", { name: "Maternity leave" });
    expect(link.getAttribute("href")).toBe(
      "/hr-admin/leave-types/2/edit"
    );
  });

  it("renders an empty state when there are no leave types", () => {
    render(<LeaveTypeTable leaveTypes={[]} />);

    expect(screen.getByText("No leave types found")).toBeInTheDocument();
  });

  it("does not let annual leave be edited from here", () => {
    render(<LeaveTypeTable leaveTypes={[annual, maternity]} />);

    // The name is plain text, not a link to the edit page.
    expect(screen.getByText("Annual leave").tagName).not.toBe("A");
    expect(
      screen.queryByRole("link", { name: "Annual leave" })
    ).not.toBeInTheDocument();
    expect(screen.getByText("Managed in Entitlements")).toBeInTheDocument();

    const editDays = screen.getByRole("link", { name: "Edit days" });
    expect(editDays.getAttribute("href")).toBe(
      "/hr-admin/entitlements"
    );
  });

  it("still offers editing for other leave types", () => {
    render(<LeaveTypeTable leaveTypes={[annual, maternity]} />);

    expect(
      screen.getByRole("link", { name: "Maternity leave" })
    ).toHaveAttribute("href", "/hr-admin/leave-types/2/edit");
    expect(
      screen.getByRole("link", { name: "Edit", description: "Edit record" })
    ).toHaveAttribute("href", "/hr-admin/leave-types/2/edit");
    expect(screen.getByText("Active")).toBeInTheDocument();
  });
});