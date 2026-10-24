import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HolidayTable } from "@/components/hr/holiday-table";
import type { Holiday } from "@/lib/financial-years";

const holiday: Holiday = {
  id: 4,
  name: "Independence Day",
  date: "2026-07-06",
  is_recurring: true,
  observed_shift: true,
  financial_year: null,
};

describe("HolidayTable", () => {
  it("renders holiday rows with name and date", () => {
    render(<HolidayTable holidays={[holiday]} />);

    expect(screen.getByText("Independence Day")).toBeInTheDocument();
    expect(screen.getByText("2026-07-06")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<HolidayTable holidays={[holiday]} />);

    const link = screen.getByRole("link", { name: "Independence Day" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/calendar/holidays/4/edit"
    );
  });

  it("offers a delete action per row", () => {
    render(<HolidayTable holidays={[holiday]} />);

    expect(
      screen.getByRole("button", { name: "Delete Independence Day" })
    ).toBeInTheDocument();
  });

  it("renders an empty state when no holidays exist", () => {
    render(<HolidayTable holidays={[]} />);

    expect(screen.getByText("No holidays")).toBeInTheDocument();
  });
});
