import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlanForm } from "@/components/plans/plan-form";
import { createPlan } from "@/lib/plans/service";

import { selectOption } from "./helpers/select";
import { pickDate, pickDateRange } from "./helpers/date";

let user: ReturnType<typeof userEvent.setup>;

vi.mock("@/lib/plans/service", () => ({
  createPlan: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

const leaveTypes = [
  { id: 1, name: "Annual Leave", code: "ANNUAL" },
  { id: 2, name: "Sick Leave", code: "SICK" },
];

/**
 * The plan period runs July 2026 to June 2027, so the calendar is repaged a
 * dozen times, and each re-render of a `react-day-picker` month costs real time
 * once the suite is running in parallel. Well past the 5s default.
 */
const CALENDAR_TIMEOUT = 20_000;

/** `typeLabel` is the visible leave type text, e.g. "Annual Leave". */
async function fillBlock(
  typeLabel: string,
  start: string,
  end: string,
  index = 0
) {
  const typeSelect = screen.getAllByLabelText("Leave type")[index];
  expect(typeSelect).toBeTruthy();
  await selectOption(typeSelect, typeLabel, { user });
  const starts = screen.getAllByLabelText("Start date");
  const ends = screen.getAllByLabelText("End date");
  pickDate(starts[index], start);
  pickDate(ends[index], end);
}

describe("PlanForm", () => {
  beforeEach(() => {
    user = userEvent.setup();
  });

  it("adds and removes dynamic blocks", () => {
    render(<PlanForm leaveTypes={leaveTypes} />);

    expect(screen.getAllByLabelText("Leave type")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Add block" }));
    expect(screen.getAllByLabelText("Leave type")).toHaveLength(2);

    const removeButtons = screen.getAllByRole("button", { name: "Remove block" });
    expect(removeButtons).toHaveLength(2);
    fireEvent.click(removeButtons[1]);
    expect(screen.getAllByLabelText("Leave type")).toHaveLength(1);
  });

  it("keeps at least one block", () => {
    render(<PlanForm leaveTypes={leaveTypes} />);
    const remove = screen.getByRole("button", { name: "Remove block" });
    expect(remove).toBeDisabled();
  });

  it("requires a leave type for every block", async () => {
    render(<PlanForm leaveTypes={leaveTypes} />);
    pickDateRange(
      screen.getByLabelText("Plan period"),
      "2026-07-01",
      "2027-06-30"
    );
    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));

    await waitFor(() =>
      expect(createPlan).not.toHaveBeenCalled()
    );
    expect(screen.getByText(/Choose a leave type for every block/)).toBeInTheDocument();
  }, CALENDAR_TIMEOUT);

  it("submits the period and blocks to createPlan", async () => {
    vi.mocked(createPlan).mockResolvedValue({
      ok: true,
      data: {
        meta: { id: "plan-1" },
      } as never,
    });

    render(<PlanForm leaveTypes={leaveTypes} />);
    pickDateRange(
      screen.getByLabelText("Plan period"),
      "2026-07-01",
      "2027-06-30"
    );
    await fillBlock("Annual Leave", "2026-10-08", "2026-10-09");

    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));

    await waitFor(() => expect(createPlan).toHaveBeenCalledWith({
      period_start: "2026-07-01",
      period_end: "2027-06-30",
      blocks: [
        { leave_type_id: 1, start_date: "2026-10-08", end_date: "2026-10-09" },
      ],
    }));
  }, CALENDAR_TIMEOUT);

  it("surfaces a create error", async () => {
    vi.mocked(createPlan).mockResolvedValue({
      ok: false,
      kind: "validation",
      message: "Period invalid",
    });

    render(<PlanForm leaveTypes={leaveTypes} />);
    pickDateRange(
      screen.getByLabelText("Plan period"),
      "2026-07-01",
      "2027-06-30"
    );
    await fillBlock("Annual Leave", "2026-10-08", "2026-10-09");
    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));

    await waitFor(() =>
      expect(screen.getByText("Period invalid")).toBeInTheDocument()
    );
  }, CALENDAR_TIMEOUT);
});