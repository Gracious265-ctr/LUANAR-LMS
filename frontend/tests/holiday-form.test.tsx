import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HolidayForm } from "@/components/hr/holiday-form";
import type { Holiday } from "@/lib/financial-years";

import { dateDisplay } from "./helpers/date";

describe("HolidayForm", () => {
  it("renders the holiday fields for a new holiday", () => {
    render(<HolidayForm />);

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Date")).toBeInTheDocument();
    expect(screen.getByLabelText("Financial year")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create holiday" })
    ).toBeInTheDocument();
  });

  it("prefills values when editing an existing holiday", () => {
    const holiday: Holiday = {
      id: 4,
      name: "Independence Day",
      date: "2026-07-06",
      is_recurring: true,
      observed_shift: true,
      financial_year: null,
    };
    render(<HolidayForm holiday={holiday} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Independence Day");
    expect(dateDisplay(screen.getByLabelText("Date"))).toBe("06 Jul 2026");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("provides a cancel link back to the calendar index", () => {
    render(<HolidayForm />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/calendar?tab=holidays"
    );
  });
});
