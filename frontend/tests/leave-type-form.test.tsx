import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeaveTypeForm } from "@/components/hr/leave-type-form";
import type { LeaveType } from "@/lib/leave-rules";

describe("LeaveTypeForm", () => {
  it("renders name and code fields for a new leave type", () => {
    render(<LeaveTypeForm />);

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Code")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create leave type" })
    ).toBeInTheDocument();
  });

  it("prefills values when editing an existing leave type", () => {
    const leaveType: LeaveType = { id: 7, name: "Maternity leave", code: "maternity" };
    render(<LeaveTypeForm leaveType={leaveType} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Maternity leave");
    expect(screen.getByLabelText("Code")).toHaveValue("maternity");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("provides a cancel link back to the leave types index", () => {
    render(<LeaveTypeForm />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/leave-types"
    );
  });

  it("does not offer an editable form for annual leave", () => {
    const leaveType: LeaveType = {
      id: 1,
      name: "Annual leave",
      code: "annual",
    };
    render(<LeaveTypeForm leaveType={leaveType} />);

    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save changes" })
    ).not.toBeInTheDocument();
  });

  it("points HR at entitlements when annual leave is opened", () => {
    const leaveType: LeaveType = {
      id: 1,
      name: "Annual leave",
      code: "annual-leave",
    };
    render(<LeaveTypeForm leaveType={leaveType} />);

    expect(
      screen.getByText(/is managed in Entitlements/i)
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Go to Entitlements" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/entitlements"
    );
  });
});