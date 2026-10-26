import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OnLeaveTable } from "@/components/leave/OnLeaveTable";
import type { OnLeaveRow } from "@/lib/on-leave";

function row(overrides: Partial<OnLeaveRow> = {}): OnLeaveRow {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    reference_number: "LUANAR-2026-0001",
    employee: {
      id: 7,
      full_name: "Amina Banda",
      designation: "Lecturer",
      team: "Registry",
      campus: "Main Campus",
    },
    leave_type: { id: 1, name: "Annual Leave" },
    start_date: "2026-10-26",
    end_date: "2026-10-28",
    working_days: 3,
    state: "on_leave",
    ...overrides,
  };
}

describe("OnLeaveTable", () => {
  it("renders the employee, their context, the leave and its dates", () => {
    render(<OnLeaveTable rows={[row()]} />);

    expect(screen.getByText("Amina Banda")).toBeInTheDocument();
    expect(
      screen.getByText("Lecturer · Registry · Main Campus")
    ).toBeInTheDocument();
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getByText("26 Oct 2026 – 28 Oct 2026")).toBeInTheDocument();
    expect(screen.getByText("3 days")).toBeInTheDocument();
    expect(screen.getByText("On leave")).toBeInTheDocument();
  });

  it("wears the state the backend calculated", () => {
    render(
      <OnLeaveTable
        rows={[
          row({ id: "a", state: "upcoming" }),
          row({ id: "b", state: "returned" }),
        ]}
      />
    );

    expect(screen.getByText("Upcoming")).toBeInTheDocument();
    expect(screen.getByText("Returned")).toBeInTheDocument();
    expect(screen.queryByText("On leave")).not.toBeInTheDocument();
  });

  it("says one day, not one days", () => {
    render(
      <OnLeaveTable
        rows={[
          row({
            id: "single",
            start_date: "2026-10-26",
            end_date: "2026-10-26",
            working_days: 1,
          }),
        ]}
      />
    );

    expect(screen.getByText("1 day")).toBeInTheDocument();
  });

  it("drops the context line when the employee has none", () => {
    render(
      <OnLeaveTable
        rows={[
          row({
            employee: {
              id: 8,
              full_name: "Grace Phiri",
              designation: "",
              team: "",
              campus: "",
            },
          }),
        ]}
      />
    );

    expect(screen.getByText("Grace Phiri")).toBeInTheDocument();
    expect(screen.queryByText(/·/)).not.toBeInTheDocument();
  });

  it("uses an em dash where the backend has no value", () => {
    render(
      <OnLeaveTable
        rows={[
          row({
            leave_type: { id: null, name: "" },
            start_date: null,
            end_date: null,
            working_days: null,
          }),
        ]}
      />
    );

    // The leave type and the dates each fall back; the days cell is the third.
    expect(screen.getAllByText("—")).toHaveLength(3);
  });

  it("renders one row per application", () => {
    render(
      <OnLeaveTable
        rows={[
          row({ id: "one" }),
          row({ id: "two", employee: { ...row().employee, id: 9, full_name: "Grace Phiri" } }),
        ]}
      />
    );

    const table = screen.getByRole("table");
    const [, body] = within(table).getAllByRole("rowgroup");

    expect(within(body).getAllByRole("row")).toHaveLength(2);
  });
});
