import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveTypeTable } from "@/components/leave-config/LeaveTypeTable";
import { ShowInactiveToggle } from "@/components/leave-config/ShowInactiveToggle";
import type { LeaveType } from "@/lib/leave-config";

const { routerMock } = vi.hoisted(() => ({
  routerMock: {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  },
}));

vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return {
    ...actual,
    useRouter: () => routerMock,
    usePathname: () => "/leave-config",
  };
});

function leaveType(overrides: Partial<LeaveType> = {}): LeaveType {
  return {
    id: 7,
    name: "Study leave",
    code: "study",
    color: "purple",
    description: "",
    branch_scope: "both",
    eligible_grades: [],
    eligible_gender: "any",
    requires_supporting_document: true,
    max_duration_days: 21,
    notice_days: 14,
    eligibility: "",
    eligibility_rules: [],
    consumes_annual_entitlement: false,
    plannable: true,
    requires_institutional_registrar_approval: false,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  routerMock.push.mockClear();
});

describe("LeaveTypeTable (spec 3.2)", () => {
  it("shows exactly the columns the spec lists", () => {
    render(<LeaveTypeTable leaveTypes={[leaveType()]} />);

    expect(
      screen.getAllByRole("columnheader").map((header) => header.textContent)
    ).toEqual([
      "Name",
      "Branch scope",
      "Max duration",
      "Notice period",
      "Document",
      "Status",
      "Last updated",
    ]);
  });

  it("renders a type as its rules, not its raw ids", () => {
    render(
      <LeaveTypeTable
        leaveTypes={[
          leaveType(),
          leaveType({
            id: 8,
            name: "Compassionate leave",
            branch_scope: "administrative",
            max_duration_days: null,
            notice_days: null,
            requires_supporting_document: false,
          }),
        ]}
      />
    );

    const [, first, second] = screen.getAllByRole("row");
    expect(within(first).getByText("Study leave")).toHaveAttribute(
      "href",
      "/leave-config/7"
    );
    expect(within(first).getByText("Both")).toBeInTheDocument();
    expect(within(first).getByText("21 days")).toBeInTheDocument();
    expect(within(first).getByText("14 days")).toBeInTheDocument();
    expect(
      within(first).getByText("Supporting document required")
    ).toBeInTheDocument();

    expect(within(second).getByText("Compassionate leave")).toHaveAttribute(
      "href",
      "/leave-config/8"
    );
    expect(within(second).getByText("Administrative")).toBeInTheDocument();
    expect(within(second).getByText("No maximum")).toBeInTheDocument();
    expect(within(second).getByText("No minimum")).toBeInTheDocument();
    expect(
      within(second).getByText("No supporting document required")
    ).toBeInTheDocument();
  });

  it("marks each row Active or Inactive rather than deleting the retired ones", () => {
    render(
      <LeaveTypeTable
        leaveTypes={[
          leaveType(),
          leaveType({ id: 8, name: "Sick leave", is_active: false }),
        ]}
      />
    );

    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    // §1.5: retired by deactivation, never by deletion — a retired type is
    // still a row, so nobody has to guess it never existed.
    expect(screen.getByText("Sick leave")).toBeInTheDocument();
  });

  it("greys a retired type in place so the list stays one list", () => {
    render(
      <LeaveTypeTable
        leaveTypes={[
          leaveType(),
          leaveType({ id: 8, name: "Sick leave", is_active: false }),
        ]}
      />
    );

    const [activeRow, inactiveRow] = screen.getAllByRole("row").slice(1);
    expect(activeRow).toHaveAttribute("data-inactive", "false");
    expect(activeRow).not.toHaveClass("opacity-60");
    expect(inactiveRow).toHaveAttribute("data-inactive", "true");
    expect(inactiveRow).toHaveClass("opacity-60");
  });

  it("dates a row by when it was last written", () => {
    render(<LeaveTypeTable leaveTypes={[leaveType()]} />);

    expect(screen.getByText(/^\d{2} \w{3} \d{4}$/)).toBeInTheDocument();
  });

  it("tells the reader what to do when the registry is empty", () => {
    render(<LeaveTypeTable leaveTypes={[]} />);

    expect(
      screen.getByText("No leave types configured yet")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Create Leave Type" })
    ).toHaveAttribute("href", "/leave-config/new");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("ShowInactiveToggle (spec 3.2)", () => {
  it("is off by default and navigates the list to include retired types", () => {
    render(<ShowInactiveToggle checked={false} />);

    const toggle = screen.getByRole("checkbox", { name: "Show inactive" });
    expect(toggle).not.toBeChecked();

    fireEvent.click(toggle);

    expect(routerMock.push).toHaveBeenCalledWith(
      "/leave-config?include_inactive=true"
    );
  });

  it("drops the query again when switched back", () => {
    render(<ShowInactiveToggle checked />);

    const toggle = screen.getByRole("checkbox", { name: "Show inactive" });
    expect(toggle).toBeChecked();

    fireEvent.click(toggle);

    expect(routerMock.push).toHaveBeenCalledWith("/leave-config");
  });
});
