import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinancialYearTable } from "@/components/hr/financial-year-table";
import type { FinancialYear } from "@/lib/financial-years";

const active: FinancialYear = {
  id: 1,
  start_date: "2025-07-01",
  end_date: "2026-06-30",
  is_active: true,
};

const upcoming: FinancialYear = {
  id: 2,
  start_date: "2027-07-01",
  end_date: "2028-06-30",
  is_active: false,
};

describe("FinancialYearTable", () => {
  it("renders financial year rows with dates and status", () => {
    render(<FinancialYearTable years={[active]} today="2026-09-17" />);

    expect(screen.getByText("2025-07-01")).toBeInTheDocument();
    expect(screen.getByText("2026-06-30")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows Upcoming for a future inactive period", () => {
    render(<FinancialYearTable years={[upcoming]} today="2026-09-17" />);

    expect(screen.getByText("Upcoming")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<FinancialYearTable years={[active]} today="2026-09-17" />);

    const link = screen.getByRole("link", { name: "2025-07-01" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/calendar/financial-years/1/edit"
    );
  });

  it("renders an empty state when no financial years exist", () => {
    render(<FinancialYearTable years={[]} today="2026-09-17" />);

    expect(
      screen.getByText("No financial years configured")
    ).toBeInTheDocument();
  });
});