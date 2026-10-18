import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { LeaveRuleTable } from "@/components/hr/leave-rule-table";
import type { LeaveRule } from "@/lib/leave-rules";

const currentRule: LeaveRule = {
  id: 1,
  leave_type: 2,
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  max_duration_days: 30,
  eligibility: "",
  min_notice_days: 5,
  requires_supporting_document: false,
  consumes_annual_entitlement: true,
  effective_from: "2026-01-01",
};

const scheduledRule: LeaveRule = {
  ...currentRule,
  id: 2,
  leave_type: 3,
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  max_duration_days: 35,
  requires_supporting_document: true,
  consumes_annual_entitlement: false,
  effective_from: "2027-01-01",
};

describe("LeaveRuleTable", () => {
  it("renders rule rows with details", () => {
    render(<LeaveRuleTable rules={[currentRule]} today="2026-09-17" />);

    expect(screen.getByText("Annual leave")).toBeInTheDocument();
    expect(screen.getByText("30 days")).toBeInTheDocument();
    expect(screen.getByText("5 days")).toBeInTheDocument();
    expect(screen.getByText("Not required")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("2026-01-01")).toBeInTheDocument();
  });

  it("shows Current for an effective rule and Scheduled for a future rule", () => {
    render(
      <LeaveRuleTable
        rules={[currentRule, scheduledRule]}
        today="2026-09-17"
      />
    );

    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows document requirement and annual consumption flags", () => {
    render(<LeaveRuleTable rules={[scheduledRule]} today="2026-09-17" />);

    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<LeaveRuleTable rules={[currentRule]} today="2026-09-17" />);

    const link = screen.getByRole("link", { name: "Annual leave" });
    expect(link.getAttribute("href")).toBe(
      "/hr-admin/leave-rules/1/edit"
    );
  });

  it("renders an empty state when there are no rules", () => {
    render(<LeaveRuleTable rules={[]} today="2026-09-17" />);

    expect(screen.getByText("No leave rules found")).toBeInTheDocument();
  });
});