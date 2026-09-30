import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { format, parseISO } from "date-fns";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

import { DelegationForm } from "@/components/hr/delegation-form";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import { openSelect, selectOption } from "./helpers/select";

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return {
    ...actual,
    createDelegation: vi.fn(),
  };
});

import { createDelegation } from "@/lib/delegations-client";

// The approvers here hold their positions as data, and their accounts carry no
// special role: that is the shape the picker now has to cope with.
const employees: Employee[] = [
  makeEmployee({ id: 3, full_name: "Jane Dean", approver_roles: ["dean"] }),
  makeEmployee({ id: 5, full_name: "Bob HOD", approver_roles: ["hod"] }),
  makeEmployee({ id: 8, full_name: "Sam Staff", approver_roles: [] }),
];

/** October 2026 is the calendar's default month, so day lookups are stable. */
const TODAY = new Date(2026, 9, 5);

/** Day buttons carry a `"PPPP"` aria-label, e.g. "Thursday, October 15th, 2026". */
function dayButton(iso: string): HTMLElement {
  return within(screen.getByRole("grid")).getByRole("button", {
    name: format(parseISO(iso), "PPPP"),
  });
}

/** Opens the period popover and picks a start day, optionally an end day. */
function pickPeriod(
  user: ReturnType<typeof userEvent.setup>,
  from: string,
  to?: string
) {
  fireEvent.click(screen.getByLabelText("Period"));
  fireEvent.click(dayButton(from));
  if (to) {
    fireEvent.click(dayButton(to));
  }
}

describe("DelegationForm", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(TODAY);
    vi.mocked(createDelegation).mockResolvedValue({
      id: 1,
      approver: 3,
      approver_name: "Jane Dean",
      approver_role: "dean",
      delegate: 5,
      delegate_name: "Bob HOD",
      starts_on: "2026-10-01",
      ends_on: "2026-11-01",
      request_reason: "Attending a conference",
      requested_by: 1,
      requested_by_name: "Aisha HR",
      decision_reason: "",
      decided_by: null,
      decided_at: null,
      status: "requested",
      state: "requested",
      created_at: "2026-09-17T12:00:00Z",
      updated_at: "2026-09-17T12:00:00Z",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the delegation request fields", () => {
    render(<DelegationForm employees={employees} />);

    expect(screen.getByLabelText("Approver")).toBeInTheDocument();
    expect(screen.getByLabelText("Delegate nomination")).toBeInTheDocument();
    expect(screen.getByLabelText("Period")).toBeInTheDocument();
    expect(screen.getByLabelText("Request reason")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create delegation request" })
    ).toBeInTheDocument();
  });

  it("only offers users with an approver role as options", async () => {
    const user = userEvent.setup();
    render(<DelegationForm employees={employees} />);

    await openSelect(screen.getByLabelText("Approver"), { user });

    expect(screen.getAllByRole("option").map((option) => option.textContent))
      .toEqual(["Select the approver", "Jane Dean", "Bob HOD"]);
  });

  it("submits the create shape with delegate and reason", async () => {
    const user = userEvent.setup();
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });
    await selectOption(
      screen.getByLabelText("Delegate nomination"),
      "Bob HOD",
      { user }
    );
    pickPeriod(user, "2026-10-01", "2026-10-15");
    fireEvent.change(screen.getByLabelText("Request reason"), {
      target: { value: "Attending a conference" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Create delegation request" })
    );

    expect(createDelegation).toHaveBeenCalledWith({
      approver: 3,
      delegate: 5,
      starts_on: "2026-10-01",
      ends_on: "2026-10-15",
      request_reason: "Attending a conference",
    });
  });

  it("sends null when no delegate nomination or end date is chosen", async () => {
    const user = userEvent.setup();
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });
    pickPeriod(user, "2026-10-01");

    fireEvent.click(
      screen.getByRole("button", { name: "Create delegation request" })
    );

    expect(createDelegation).toHaveBeenCalledWith({
      approver: 3,
      delegate: null,
      starts_on: "2026-10-01",
      ends_on: null,
      request_reason: "",
    });
  });

  it("drops the nominated approver from the delegate list", async () => {
    const user = userEvent.setup();
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });
    await openSelect(screen.getByLabelText("Delegate nomination"), { user });

    expect(
      screen.getAllByRole("option").map((option) => option.textContent)
    ).toEqual(["No nomination", "Bob HOD"]);
  });

  it("refuses to submit without a start date", async () => {
    const user = userEvent.setup();
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });

    fireEvent.click(
      screen.getByRole("button", { name: "Create delegation request" })
    );

    expect(createDelegation).not.toHaveBeenCalled();
    expect(screen.getByText("Choose a start date.")).toBeInTheDocument();
  });

  it("provides a cancel link back to the delegations index", () => {
    render(<DelegationForm employees={employees} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/delegations"
    );
  });
});
