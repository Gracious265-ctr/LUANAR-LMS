import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CalendarMonthGrid } from "@/components/hr/CalendarMonthGrid";
import type { CalendarEvent, ResolvedHoliday } from "@/lib/financial-years";
import type { WorkingDayPattern } from "@/lib/calendar-weekdays";

const workingDays: WorkingDayPattern = {
  monday: true,
  tuesday: true,
  wednesday: true,
  thursday: true,
  friday: true,
  saturday: false,
  sunday: false,
};

const holiday: ResolvedHoliday = {
  date: "2026-07-06",
  name: "Independence Day",
  is_recurring: false,
  observed_shift: true,
  holiday_id: 1,
};

const event: CalendarEvent = {
  id: 9,
  title: "Graduation week",
  start_date: "2026-07-06",
  end_date: "2026-07-10",
  description: "",
  affects_leave_calculation: false,
};

describe("CalendarMonthGrid", () => {
  it("names the shown month", () => {
    render(
      <CalendarMonthGrid
        year={2026}
        month={7}
        holidays={[]}
        events={[]}
        workingDays={workingDays}
      />
    );

    expect(screen.getByText("July 2026")).toBeInTheDocument();
  });

  it("shows resolved holidays and overlapping events", () => {
    render(
      <CalendarMonthGrid
        year={2026}
        month={7}
        holidays={[holiday]}
        events={[event]}
        workingDays={workingDays}
      />
    );

    expect(screen.getByText("Independence Day")).toBeInTheDocument();
    // The event spans five days, so its title renders in each of their cells.
    expect(screen.getAllByText("Graduation week").length).toBeGreaterThan(0);
  });

  it("ignores events outside the shown month", () => {
    render(
      <CalendarMonthGrid
        year={2026}
        month={7}
        holidays={[]}
        events={[
          {
            ...event,
            start_date: "2025-01-01",
            end_date: "2025-01-02",
          },
        ]}
        workingDays={workingDays}
      />
    );

    expect(screen.queryByText("Graduation week")).not.toBeInTheDocument();
  });
});
