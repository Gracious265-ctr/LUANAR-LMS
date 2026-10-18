import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinancialYearForm } from "@/components/hr/financial-year-form";
import type { FinancialYear } from "@/lib/financial-years";

import { dateDisplay } from "./helpers/date";

describe("FinancialYearForm", () => {
  it("renders date fields and an inactive checkbox for a new period", () => {
    render(<FinancialYearForm />);

    expect(screen.getByLabelText("Period")).toBeInTheDocument();
    expect(screen.getByLabelText("Active financial year")).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Create financial year" })
    ).toBeInTheDocument();
  });

  it("prefills values when editing an existing period", () => {
    const year: FinancialYear = {
      id: 2,
      start_date: "2026-07-01",
      end_date: "2027-06-30",
      is_active: true,
    };
    render(<FinancialYearForm financialYear={year} />);

    expect(dateDisplay(screen.getByLabelText("Period"))).toBe(
      "01 Jul 2026 – 30 Jun 2027"
    );
    expect(screen.getByLabelText("Active financial year")).toBeChecked();
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("provides a cancel link back to the calendar index", () => {
    render(<FinancialYearForm />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe("/hr-admin/calendar");
  });
});