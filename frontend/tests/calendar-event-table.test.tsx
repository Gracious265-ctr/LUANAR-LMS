import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CalendarEventTable } from "@/components/hr/calendar-event-table";
import type { CalendarEvent } from "@/lib/financial-years";

const event: CalendarEvent = {
  id: 3,
  title: "Graduation week",
  start_date: "2026-07-06",
  end_date: "2026-07-10",
  description: "Ceremonies all week.",
  affects_leave_calculation: false,
};

describe("CalendarEventTable", () => {
  it("renders events with their period", () => {
    render(<CalendarEventTable events={[event]} />);

    expect(screen.getByText("Graduation week")).toBeInTheDocument();
    expect(screen.getByText("2026-07-06 – 2026-07-10")).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<CalendarEventTable events={[event]} />);

    const link = screen.getByRole("link", { name: "Graduation week" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/calendar/events/3/edit"
    );
  });

  it("renders an empty state when no events exist", () => {
    render(<CalendarEventTable events={[]} />);

    expect(screen.getByText("No events")).toBeInTheDocument();
  });
});
