import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/hooks/useTeamPlans", () => ({ useTeamPlans: vi.fn() }));

import { TeamPlansCalendar } from "@/components/plans/TeamPlansCalendar";
import { useTeamPlans } from "@/lib/hooks/useTeamPlans";
import { makePlan, makeScope, makeTeamPlans } from "@/lib/plans/__fixtures__";

function mockTeam(over: Record<string, unknown> = {}) {
  const shiftMonth = vi.fn();
  const setScope = vi.fn();
  vi.mocked(useTeamPlans).mockReturnValue({
    scopes: [makeScope()],
    scope: "team:1",
    setScope,
    scopesLoaded: true,
    month: "2026-11",
    shiftMonth,
    data: makeTeamPlans(),
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    ...over,
  } as unknown as ReturnType<typeof useTeamPlans>);
  return { shiftMonth, setScope };
}

beforeEach(() => {
  vi.mocked(useTeamPlans).mockReset();
});

describe("TeamPlansCalendar", () => {
  it("renders the month label and a day cell per day", () => {
    mockTeam();
    render(<TeamPlansCalendar />);

    expect(screen.getByText("November 2026")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "2 November 2026" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "30 November 2026" })
    ).toBeInTheDocument();
  });

  it("pages months", () => {
    const { shiftMonth } = mockTeam();
    render(<TeamPlansCalendar />);

    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(shiftMonth).toHaveBeenCalledWith(-1);

    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
    expect(shiftMonth).toHaveBeenCalledWith(1);
  });

  it("hides the scope selector when there is only one scope", () => {
    mockTeam();
    render(<TeamPlansCalendar />);
    expect(screen.queryByLabelText("Calendar scope")).not.toBeInTheDocument();
  });

  it("shows the scope selector when the scope list widens", () => {
    mockTeam({
      scopes: [makeScope(), makeScope({ id: "institution", label: "Institution-wide" })],
    });
    render(<TeamPlansCalendar />);
    expect(screen.getByLabelText("Calendar scope")).toBeInTheDocument();
  });

  it("draws an employee's bar across every day their plan spans", () => {
    mockTeam({
      data: makeTeamPlans({
        results: [
          makePlan({
            id: "p1",
            employee_name: "Chisomo Phiri",
            planned_start_date: "2026-11-10",
            planned_end_date: "2026-11-12",
          }),
        ],
      }),
    });
    render(<TeamPlansCalendar />);

    // 11 Nov is inside the range; 15 Nov is outside it.
    const inside = screen.getByRole("button", { name: "11 November 2026" });
    expect(inside).toHaveTextContent("Chisomo Phiri");
    const outside = screen.getByRole("button", { name: "15 November 2026" });
    expect(outside).not.toHaveTextContent("Chisomo Phiri");
  });

  it("opens a day overlay listing the plans touching that day", () => {
    mockTeam({
      data: makeTeamPlans({
        results: [
          makePlan({
            id: "p1",
            employee_name: "Chisomo Phiri",
            leave_type_name: "Annual Leave",
            planned_start_date: "2026-11-10",
            planned_end_date: "2026-11-12",
          }),
        ],
      }),
    });
    render(<TeamPlansCalendar />);

    fireEvent.click(screen.getByRole("button", { name: "11 November 2026" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Chisomo Phiri")).toBeInTheDocument();
  });

  it("shows an empty state for a month with no plans", () => {
    mockTeam();
    render(<TeamPlansCalendar />);
    expect(screen.getByText(/no planned leave this month/i)).toBeInTheDocument();
  });

  it("shows a friendly empty state when the viewer has no team scope", () => {
    mockTeam({ scopes: [], scope: null, scopesLoaded: true, data: null });
    render(<TeamPlansCalendar />);

    expect(screen.getByText(/no team to show yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/couldn't load the calendar/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no planned leave this month/i)).not.toBeInTheDocument();
  });

  it("shows the calendar skeleton, not the empty state, while scopes load", () => {
    mockTeam({ scopes: [], scope: null, scopesLoaded: false, isLoading: true, data: null });
    render(<TeamPlansCalendar />);

    expect(screen.queryByText(/no team to show yet/i)).not.toBeInTheDocument();
  });

  it("shows an error state when the calendar failed to load", () => {
    mockTeam({ data: null, error: "nope" });
    render(<TeamPlansCalendar />);
    expect(screen.getByText(/couldn't load the calendar/i)).toBeInTheDocument();
  });
});
