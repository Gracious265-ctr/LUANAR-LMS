import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkingDaysSection } from "@/components/hr/WorkingDaysSection";
import type { WorkingDayPattern } from "@/lib/calendar-weekdays";

const weekdaysOnly: WorkingDayPattern = {
  monday: true,
  tuesday: true,
  wednesday: true,
  thursday: true,
  friday: true,
  saturday: false,
  sunday: false,
};

describe("WorkingDaysSection", () => {
  it("renders a checkbox per weekday reflecting the current pattern", () => {
    render(<WorkingDaysSection pattern={weekdaysOnly} />);

    expect(screen.getByLabelText("Monday")).toBeChecked();
    expect(screen.getByLabelText("Friday")).toBeChecked();
    expect(screen.getByLabelText("Saturday")).not.toBeChecked();
    expect(screen.getByLabelText("Sunday")).not.toBeChecked();
  });

  it("offers a save action", () => {
    render(<WorkingDaysSection pattern={weekdaysOnly} />);

    expect(
      screen.getByRole("button", { name: "Save working days" })
    ).toBeInTheDocument();
  });
});
