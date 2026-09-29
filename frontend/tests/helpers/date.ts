import { fireEvent, screen } from "@testing-library/react";
import { format, parse, parseISO, startOfMonth } from "date-fns";

/**
 * Drives the shared `DatePicker` / `DateRangePicker` popovers.
 *
 * Both pickers render a `Button` trigger plus a `react-day-picker` calendar in
 * a popover, so the native `<input type="date">` helpers do not apply: there is
 * no `change` event to fire and no value to read back. Open the trigger, page
 * the calendar to the wanted month, then activate the day button.
 *
 * This is all `fireEvent` rather than `userEvent`: a plan period can sit a year
 * away from today, and simulating a full pointer sequence for each of a dozen
 * paging clicks pushed whole test files past their per-test timeout.
 */

/** The most months the helper will page through before giving up. */
const MAX_PAGE_STEPS = 14;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Day buttons carry a `"PPPP"` label; today's cell is prefixed with "Today,". */
function dayButton(iso: string): HTMLElement | null {
  return screen.queryByRole("button", {
    name: new RegExp(escapeRegExp(format(parseISO(iso), "PPPP"))),
  });
}

/** The month the open grid is showing, parsed from its `"September 2026"` label. */
function displayedMonth(): Date {
  const label = screen.getByRole("grid").getAttribute("aria-label") ?? "";
  const month = parse(label, "MMMM yyyy", new Date());
  if (Number.isNaN(month.getTime())) {
    throw new Error(`Unreadable calendar label: "${label}".`);
  }
  return startOfMonth(month);
}

/** Opens a picker popover. */
export function openDatePicker(trigger: HTMLElement) {
  fireEvent.click(trigger);
}

/** Closes a picker popover that is still open, e.g. an open-ended range. */
export function closeDatePicker(trigger: HTMLElement) {
  fireEvent.click(trigger);
}

/**
 * Activates `iso` in the calendar that is already open, paging the month
 * towards it. The grid label (`"September 2026"`) is where the direction comes
 * from, and the day is often on screen already, since a grid shows its
 * neighbours' edge days.
 */
export function chooseDay(iso: string) {
  const onScreen = dayButton(iso);
  if (onScreen) {
    fireEvent.click(onScreen);
    return;
  }

  const target = startOfMonth(parseISO(iso));
  const direction =
    target < startOfMonth(displayedMonth()) ? "Previous" : "Next";

  let previous = displayedMonth().getTime();
  for (let step = 0; step < MAX_PAGE_STEPS; step += 1) {
    fireEvent.click(
      screen.getByRole("button", { name: `Go to the ${direction} Month` })
    );
    const current = displayedMonth().getTime();
    if (current === previous) break;
    previous = current;

    const day = dayButton(iso);
    if (day) {
      fireEvent.click(day);
      return;
    }
  }

  throw new Error(`Could not reach ${iso} in the calendar.`);
}

/** Opens the trigger and picks a single date; the picker closes itself. */
export function pickDate(trigger: HTMLElement, iso: string) {
  openDatePicker(trigger);
  chooseDay(iso);
}

/**
 * Opens the trigger and picks only the range's start date, leaving it
 * open-ended. The popover stays open after the first click, so it is dismissed
 * here — otherwise the next picker in the test would open alongside a stale
 * calendar.
 */
export function pickRangeStart(trigger: HTMLElement, iso: string) {
  openDatePicker(trigger);
  chooseDay(iso);
  closeDatePicker(trigger);
}

/** Opens the trigger and picks a closed range, which closes the popover. */
export function pickDateRange(trigger: HTMLElement, from: string, to: string) {
  openDatePicker(trigger);
  chooseDay(from);
  chooseDay(to);
}

/**
 * The visible text on a picker trigger, e.g. `"01 Jul 2026"` for a single date
 * or `"01 Jul 2026 – 30 Jun 2027"` for a closed range.
 */
export function dateDisplay(trigger: HTMLElement): string {
  return trigger.textContent?.trim() ?? "";
}
