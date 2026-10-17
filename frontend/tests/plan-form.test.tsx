import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  usePathname: () => "/dashboard/plans/new",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/services/leaveTypes", () => ({
  getPlannableLeaveTypes: vi.fn(),
}));

vi.mock("@/lib/plans/service", () => ({ createPlan: vi.fn() }));

// The real picker is a Radix calendar; the form only cares that it emits a
// from/to pair, so the test drives it with a single button.
vi.mock("@/components/ui/date-picker", () => ({
  DateRangePicker: (props: { onRangeChange: (f: string, t: string) => void }) => (
    <button
      type="button"
      onClick={() => props.onRangeChange("2026-11-02", "2026-11-06")}
    >
      pick-dates
    </button>
  ),
}));

import { CreatePlanForm } from "@/components/plans/CreatePlanForm";
import { getPlannableLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";
import { createPlan } from "@/lib/plans/service";
import { makePlan } from "@/lib/plans/__fixtures__";
import { selectOption } from "./helpers/select";

const TYPES: LeaveType[] = [
  { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: null, plannable: true, planNoticeDays: 14 },
  { id: 2, name: "Study Leave", requiresDocuments: false, maxDurationDays: null, plannable: true, planNoticeDays: 30 },
];

beforeEach(() => {
  vi.mocked(getPlannableLeaveTypes).mockReset();
  vi.mocked(createPlan).mockReset();
  push.mockReset();
  vi.mocked(getPlannableLeaveTypes).mockResolvedValue(TYPES);
});

describe("CreatePlanForm", () => {
  it("pre-selects the leave type passed in (re-planning a missed plan)", async () => {
    render(<CreatePlanForm initialLeaveType={2} />);
    expect(await screen.findByRole("combobox", { name: "Leave type" })).toHaveTextContent(
      "Study Leave"
    );
  });

  it("leaves the leave type unchosen until the user picks one", async () => {
    render(<CreatePlanForm />);
    const trigger = screen.getByRole("combobox", { name: "Leave type" });
    await waitFor(() => expect(trigger).toHaveTextContent("Select a leave type"));
    expect(screen.getByRole("button", { name: /save plan/i })).toBeDisabled();
  });

  it("shows the reminder window as the field hint", async () => {
    render(<CreatePlanForm initialLeaveType={1} />);
    expect(
      await screen.findByText(/a reminder fires 14 days before the start date/i)
    ).toBeInTheDocument();
  });

  it("keeps Save disabled until a type and both dates are chosen", async () => {
    render(<CreatePlanForm initialLeaveType={1} />);
    const save = await screen.findByRole("button", { name: /save plan/i });
    expect(save).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "pick-dates" }));
    await waitFor(() => expect(save).toBeEnabled());
  });

  it("creates the plan and returns to My Plans on success", async () => {
    vi.mocked(createPlan).mockResolvedValue(makePlan());
    render(<CreatePlanForm initialLeaveType={1} />);

    fireEvent.click(await screen.findByRole("button", { name: "pick-dates" }));
    fireEvent.click(screen.getByRole("button", { name: /save plan/i }));

    await waitFor(() =>
      expect(createPlan).toHaveBeenCalledWith({
        leave_type: 1,
        planned_start_date: "2026-11-02",
        planned_end_date: "2026-11-06",
        notes: "",
      })
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard/plans"));
  });

  it("stays put and shows the overlap warning instead of navigating", async () => {
    vi.mocked(createPlan).mockResolvedValue(
      makePlan({ overlap_warning: "This overlaps Chisomo's leave." })
    );
    render(<CreatePlanForm initialLeaveType={1} />);

    fireEvent.click(await screen.findByRole("button", { name: "pick-dates" }));
    fireEvent.click(screen.getByRole("button", { name: /save plan/i }));

    expect(
      await screen.findByText("This overlaps Chisomo's leave.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("lets the user change the leave type through the select", async () => {
    vi.mocked(createPlan).mockResolvedValue(makePlan());
    render(<CreatePlanForm initialLeaveType={1} />);

    const trigger = screen.getByRole("combobox", { name: "Leave type" });
    await waitFor(() => expect(trigger).toHaveTextContent("Annual Leave"));
    await selectOption(trigger, "Study Leave");
    fireEvent.click(screen.getByRole("button", { name: "pick-dates" }));
    fireEvent.click(screen.getByRole("button", { name: /save plan/i }));

    await waitFor(() =>
      expect(createPlan).toHaveBeenCalledWith(
        expect.objectContaining({ leave_type: 2 })
      )
    );
  });

  it("reports a save failure", async () => {
    vi.mocked(createPlan).mockRejectedValue(new Error("Leave type is not plannable."));
    render(<CreatePlanForm initialLeaveType={1} />);

    fireEvent.click(await screen.findByRole("button", { name: "pick-dates" }));
    fireEvent.click(screen.getByRole("button", { name: /save plan/i }));

    expect(
      await screen.findByText("Leave type is not plannable.")
    ).toBeInTheDocument();
  });
});
