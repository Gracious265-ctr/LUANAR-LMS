import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PublicHolidayForm } from "@/components/hr/public-holiday-form";
import type { PublicHoliday } from "@/lib/financial-years";

describe("PublicHolidayForm", () => {
  it("renders name and date fields for a new holiday", () => {
    render(<PublicHolidayForm />);

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Date")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create holiday" })
    ).toBeInTheDocument();
  });

  it("prefills values when editing an existing holiday", () => {
    const holiday: PublicHoliday = {
      id: 4,
      name: "Independence Day",
      date: "2026-07-06",
    };
    render(<PublicHolidayForm publicHoliday={holiday} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Independence Day");
    expect(screen.getByLabelText("Date")).toHaveValue("2026-07-06");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("provides a cancel link back to the calendar index", () => {
    render(<PublicHolidayForm />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe("/dashboard/hr-admin/calendar");
  });
});