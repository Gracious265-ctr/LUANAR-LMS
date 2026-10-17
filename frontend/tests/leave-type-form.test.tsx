import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/leave-rules-client", () => ({
  createLeaveType: vi.fn(),
  updateLeaveType: vi.fn(),
}));

import { LeaveTypeForm } from "@/components/hr/leave-type-form";
import { createLeaveType } from "@/lib/leave-rules-client";
import type { LeaveType } from "@/lib/leave-rules";

beforeEach(() => {
  vi.mocked(createLeaveType).mockReset();
});

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

  it("defaults a new type to plannable with no reminder window", () => {
    render(<LeaveTypeForm />);

    expect(screen.getByLabelText(/Plannable/)).toBeChecked();
    expect(screen.getByLabelText("Plan reminder notice (days)")).toBeInTheDocument();
  });

  it("prefills the planning fields when editing", () => {
    const leaveType: LeaveType = {
      id: 9,
      name: "Study leave",
      code: "study",
      plannable: false,
      plan_notice_days: 10,
    };
    render(<LeaveTypeForm leaveType={leaveType} />);

    expect(screen.getByLabelText(/Plannable/)).not.toBeChecked();
    expect(screen.getByLabelText("Plan reminder notice (days)")).toHaveValue(10);
  });

  it("submits the planning fields with the rest of the type", async () => {
    vi.mocked(createLeaveType).mockResolvedValue({
      id: 3,
      name: "Study leave",
      code: "study",
    });
    const onSuccess = vi.fn();
    render(<LeaveTypeForm onSuccess={onSuccess} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Study leave" },
    });
    fireEvent.change(screen.getByLabelText("Plan reminder notice (days)"), {
      target: { value: "21" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create leave type" }));

    await waitFor(() =>
      expect(createLeaveType).toHaveBeenCalledWith(
        expect.objectContaining({ plannable: true, plan_notice_days: 21 })
      )
    );
  });

  it("sends null for an empty reminder window", async () => {
    vi.mocked(createLeaveType).mockResolvedValue({
      id: 3,
      name: "Study leave",
      code: "study",
    });
    render(<LeaveTypeForm onSuccess={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Study leave" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create leave type" }));

    await waitFor(() =>
      expect(createLeaveType).toHaveBeenCalledWith(
        expect.objectContaining({ plan_notice_days: null })
      )
    );
  });
});