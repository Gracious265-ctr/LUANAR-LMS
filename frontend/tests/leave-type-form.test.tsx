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
});