import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PublicHolidayTable } from "@/components/hr/public-holiday-table";
import type { PublicHoliday } from "@/lib/financial-years";

const holiday: PublicHoliday = {
  id: 4,
  name: "Independence Day",
  date: "2026-07-06",
};

describe("PublicHolidayTable", () => {
  it("renders holiday rows with name and date", () => {
    render(<PublicHolidayTable holidays={[holiday]} />);

    expect(screen.getByText("Independence Day")).toBeInTheDocument();
    expect(screen.getByText("2026-07-06")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<PublicHolidayTable holidays={[holiday]} />);

    const link = screen.getByRole("link", { name: "Independence Day" });
    expect(link.getAttribute("href")).toBe(
      "/hr-admin/calendar/holidays/4/edit"
    );
  });

  it("renders an empty state when no holidays exist", () => {
    render(<PublicHolidayTable holidays={[]} />);

    expect(screen.getByText("No public holidays")).toBeInTheDocument();
  });
});