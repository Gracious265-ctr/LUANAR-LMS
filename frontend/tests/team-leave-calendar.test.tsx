import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamLeaveCalendar } from "@/components/calendar/TeamLeaveCalendar";
import { fetchTeamCalendar } from "@/lib/calendar/service";
import type { TeamCalendarResponse } from "@/lib/calendar/types";

vi.mock("@/lib/calendar/service", () => ({
  fetchTeamCalendar: vi.fn(),
}));

const mockedFetch = vi.mocked(fetchTeamCalendar);

function payload(
  overrides: Partial<TeamCalendarResponse> = {}
): TeamCalendarResponse {
  return {
    unit_id: 7,
    unit_name: "Finance",
    month: "2026-10",
    team_size: 5,
    conflict_threshold: 2,
    entries: [
      {
        id: "app-a",
        employee: { id: 1, name: "Alice Anderson" },
        start_date: "2026-10-05",
        end_date: "2026-10-07",
        leave_type: { id: 1, code: "ANNUAL", name: "Annual Leave" },
        status: "approved",
      },
      {
        id: "app-b",
        employee: { id: 2, name: "Bob Brown" },
        start_date: "2026-10-06",
        end_date: "2026-10-08",
        leave_type: { id: 2, code: "SICK", name: "Sick Leave" },
        status: "pending",
      },
      {
        id: "app-c",
        employee: { id: 3, name: "Carol Clark" },
        start_date: "2026-10-06",
        end_date: "2026-10-06",
        leave_type: { id: 3, code: "STUDY", name: "Study Leave" },
        status: "approved",
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("TeamLeaveCalendar", () => {
  it("draws one row per member with approved and pending bars", async () => {
    mockedFetch.mockResolvedValue({ ok: true, data: payload() });
    render(<TeamLeaveCalendar unitId={7} initialMonth="2026-10" />);

    expect(await screen.findByText("Alice Anderson")).toBeInTheDocument();
    expect(screen.getByText("Bob Brown")).toBeInTheDocument();
    expect(screen.getByText("Carol Clark")).toBeInTheDocument();

    expect(
      document.querySelectorAll('[data-testid^="calendar-bar-"]')
    ).toHaveLength(3);
    expect(
      document.querySelectorAll('[data-status="pending"]')
    ).toHaveLength(1);
    expect(await screen.findByText("October 2026")).toBeInTheDocument();
  });

  it("stripes days where the team is over the cap", async () => {
    mockedFetch.mockResolvedValue({ ok: true, data: payload() });
    render(<TeamLeaveCalendar unitId={7} initialMonth="2026-10" />);

    // Oct 6 has three people out against a cap of two; Oct 7 has two, so it is
    // within the cap and must not be striped.
    expect(
      await screen.findByText("Alice Anderson")
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-conflict-day="2026-10-06"]')
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-conflict-day="2026-10-07"]')
    ).not.toBeInTheDocument();
  });

  it("ring-highlights the application under review", async () => {
    mockedFetch.mockResolvedValue({ ok: true, data: payload() });
    render(
      <TeamLeaveCalendar
        unitId={7}
        initialMonth="2026-10"
        highlightEntryId="app-b"
      />
    );

    const bar = await screen.findByTestId("calendar-bar-app-b");
    expect(bar.className).toContain("ring-2");
    expect(screen.getByTestId("calendar-bar-app-a").className).not.toContain(
      "ring-2"
    );
  });

  it("shows the empty state when nobody is away", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      data: payload({ entries: [] }),
    });
    render(<TeamLeaveCalendar unitId={7} initialMonth="2026-10" />);

    expect(
      await screen.findByText("No leave scheduled this month.")
    ).toBeInTheDocument();
  });

  it("navigates months and re-fetches", async () => {
    mockedFetch.mockResolvedValue({ ok: true, data: payload() });
    render(<TeamLeaveCalendar unitId={7} initialMonth="2026-10" />);
    await screen.findByText("October 2026");

    fireEvent.click(screen.getByRole("button", { name: "Next month" }));

    expect(await screen.findByText("November 2026")).toBeInTheDocument();
    await waitFor(() =>
      expect(mockedFetch).toHaveBeenCalledWith(7, "2026-11")
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(await screen.findByText("October 2026")).toBeInTheDocument();
  });

  it("reports the loaded payload to its parent", async () => {
    const data = payload();
    mockedFetch.mockResolvedValue({ ok: true, data });
    const onData = vi.fn();
    render(
      <TeamLeaveCalendar unitId={7} initialMonth="2026-10" onData={onData} />
    );

    await waitFor(() => expect(onData).toHaveBeenCalledWith(data));
  });

  it("shows a not-found note when the calendar is out of reach", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      kind: "not_found",
      message: "This team's calendar is not available to you.",
    });
    render(<TeamLeaveCalendar unitId={7} initialMonth="2026-10" />);

    expect(
      await screen.findByText("This team's calendar is not available to you.")
    ).toBeInTheDocument();
  });
});
