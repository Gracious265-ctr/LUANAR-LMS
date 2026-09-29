import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { LeaveRuleForm } from "@/components/hr/leave-rule-form";
import type { LeaveRule, LeaveType } from "@/lib/leave-rules";

import { openSelect, selectedValue } from "./helpers/select";

let user: ReturnType<typeof userEvent.setup>;

const leaveTypes: LeaveType[] = [
  { id: 1, name: "Annual leave", code: "annual" },
  { id: 2, name: "Maternity leave", code: "maternity" },
  { id: 3, name: "Paternity leave", code: "paternity" },
];

const rule: LeaveRule = {
  id: 5,
  leave_type: 2,
  leave_type_code: "maternity",
  leave_type_name: "Maternity leave",
  max_duration_days: 90,
  eligibility: "Female employees",
  min_notice_days: 5,
  requires_supporting_document: true,
  consumes_annual_entitlement: false,
  effective_from: "2026-01-01",
};

describe("LeaveRuleForm", () => {
  beforeEach(() => {
    user = userEvent.setup();
  });

  it("renders rule fields for a new rule", () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    expect(screen.getByLabelText("Leave type")).toBeInTheDocument();
    expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument();
    expect(screen.getByLabelText("Minimum notice (days)")).toBeInTheDocument();
    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.getByLabelText("Eligibility")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create rule" })).toBeInTheDocument();
  });

  it("offers every leave type in the dropdown", async () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    await openSelect(screen.getByLabelText("Leave type"), { user });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("Annual leave");
    expect(options).toContain("Maternity leave");
    expect(options).toContain("Paternity leave");
  });

  it("prefills values when editing an existing rule", () => {
    render(<LeaveRuleForm leaveRule={rule} leaveTypes={leaveTypes} />);

    expect(screen.getByLabelText("Maximum duration (days)")).toHaveValue(90);
    expect(screen.getByLabelText("Minimum notice (days)")).toHaveValue(5);
    expect(screen.getByLabelText("Effective from")).toHaveValue("2026-01-01");
    expect(screen.getByLabelText("Eligibility")).toHaveValue("Female employees");
    expect(selectedValue(screen.getByLabelText("Leave type"))).toBe(
      "Maternity leave"
    );
    expect(
      screen.getByLabelText("Requires a supporting document")
    ).toBeChecked();
    expect(
      screen.getByLabelText("Consumes annual leave entitlement")
    ).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });

  it("provides a cancel link back to the leave rules index", () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/leave-rules"
    );
  });
});