import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { EntitlementTable } from "@/components/hr/entitlement-table";
import type { Entitlement } from "@/lib/entitlements";

const currentEntitlement: Entitlement = {
  id: 1,
  grade_start: "A",
  grade_end: "C",
  days: 21,
  effective_from: "2026-01-01",
  leave_type: null,
  leave_type_name: null,
};

const scheduledEntitlement: Entitlement = {
  id: 2,
  grade_start: "H",
  grade_end: "U",
  days: 30,
  effective_from: "2027-01-01",
  leave_type: null,
  leave_type_name: null,
};

describe("EntitlementTable", () => {
  it("renders entitlement rows with details", () => {
    render(<EntitlementTable entitlements={[currentEntitlement]} />);

    expect(screen.getByText("A–C")).toBeInTheDocument();
    expect(screen.getByText("21 days")).toBeInTheDocument();
    expect(screen.getByText("2026-01-01")).toBeInTheDocument();
  });

  it("shows Current for an effective rule and Scheduled for a future rule", () => {
    render(
      <EntitlementTable
        entitlements={[currentEntitlement, scheduledEntitlement]}
      />
    );

    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<EntitlementTable entitlements={[currentEntitlement]} />);

    const link = screen.getByRole("link", { name: "A–C" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/entitlements/1/edit"
    );
  });

  it("renders an empty state when there are no rules", () => {
    render(<EntitlementTable entitlements={[]} />);

    expect(screen.getByText("No entitlement rules found")).toBeInTheDocument();
  });
});