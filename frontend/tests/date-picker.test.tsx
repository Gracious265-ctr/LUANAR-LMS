import { fireEvent, render, screen, within } from "@testing-library/react";
import { format, parseISO } from "date-fns";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DatePicker, DateRangePicker } from "@/components/ui/date-picker";
import { Field } from "@/components/ui/input";

/** October 2026 is the calendar's default month, so day lookups are stable. */
const TODAY = new Date(2026, 9, 5);

/** Day buttons carry a `"PPPP"` aria-label, e.g. "Thursday, October 15th, 2026". */
function dayButton(iso: string): HTMLElement {
  return within(screen.getByRole("grid")).getByRole("button", {
    name: format(parseISO(iso), "PPPP"),
  });
}

describe("DatePicker", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(TODAY);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a placeholder until a date is chosen", () => {
    render(<DatePicker onChange={vi.fn()} placeholder="Pick a day" />);

    expect(
      screen.getByRole("button", { name: "Pick a day" })
    ).toBeInTheDocument();
  });

  it("formats an existing ISO value for display", () => {
    render(<DatePicker value="2026-10-15" onChange={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: "15 Oct 2026" })
    ).toBeInTheDocument();
  });

  it("emits an ISO date when a day is clicked", () => {
    const onChange = vi.fn();
    render(<DatePicker value="2026-10-15" onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "15 Oct 2026" }));
    fireEvent.click(dayButton("2026-10-20"));

    expect(onChange).toHaveBeenCalledWith("2026-10-20");
  });

  it("disables days outside the inclusive min and max bounds", () => {
    render(
      <DatePicker
        value="2026-10-15"
        onChange={vi.fn()}
        min="2026-10-10"
        max="2026-10-25"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "15 Oct 2026" }));

    expect(dayButton("2026-10-09")).toBeDisabled();
    expect(dayButton("2026-10-10")).toBeEnabled();
    expect(dayButton("2026-10-25")).toBeEnabled();
    expect(dayButton("2026-10-26")).toBeDisabled();
  });

  it("is reachable from a Field label", () => {
    render(
      <Field label="Start Date" htmlFor="start">
        <DatePicker id="start" value="2026-10-15" onChange={vi.fn()} />
      </Field>
    );

    expect(screen.getByLabelText("Start Date")).toHaveTextContent("15 Oct 2026");
  });
});

describe("DateRangePicker", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(TODAY);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("emits both ends of the range once a start and an end are picked", () => {
    const onRangeChange = vi.fn();
    render(<DateRangePicker onRangeChange={onRangeChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Select date range" }));
    fireEvent.click(dayButton("2026-10-15"));
    fireEvent.click(dayButton("2026-10-20"));

    expect(onRangeChange).toHaveBeenNthCalledWith(1, "2026-10-15", "");
    expect(onRangeChange).toHaveBeenNthCalledWith(2, "2026-10-15", "2026-10-20");
  });

  it("starts a fresh range when a complete range is already set", () => {
    const onRangeChange = vi.fn();
    render(
      <DateRangePicker
        from="2026-10-15"
        to="2026-10-20"
        onRangeChange={onRangeChange}
      />
    );

    const trigger = screen.getByRole("button", {
      name: "15 Oct 2026 – 20 Oct 2026",
    });
    expect(trigger).toBeInTheDocument();

    fireEvent.click(trigger);
    fireEvent.click(dayButton("2026-10-22"));

    expect(onRangeChange).toHaveBeenCalledWith("2026-10-22", "");
  });

  it("normalises a backwards selection so the start never follows the end", () => {
    const onRangeChange = vi.fn();
    render(<DateRangePicker onRangeChange={onRangeChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Select date range" }));
    fireEvent.click(dayButton("2026-10-20"));
    fireEvent.click(dayButton("2026-10-12"));

    expect(onRangeChange).toHaveBeenNthCalledWith(2, "2026-10-12", "2026-10-20");
  });

  it("shows an open-ended range while only a start is set", () => {
    render(
      <DateRangePicker from="2026-10-15" to="" onRangeChange={vi.fn()} />
    );

    expect(
      screen.getByRole("button", { name: "15 Oct 2026 – …" })
    ).toBeInTheDocument();
  });
});
