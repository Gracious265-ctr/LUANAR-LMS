import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { DelegationForm } from "@/components/hr/delegation-form";
import type { Employee, UserRole } from "@/lib/employees";

import { openSelect, selectOption } from "./helpers/select";
import { pickDateRange, pickRangeStart } from "./helpers/date";

let user: ReturnType<typeof userEvent.setup>;

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return {
    ...actual,
    createDelegation: vi.fn(),
  };
});

import { createDelegation } from "@/lib/delegations-client";

function makeEmployee(id: number, role: UserRole, name: string): Employee {
  return {
    id,
    user_id: id,
    email: `${name.replace(" ", ".").toLowerCase()}@test.luanar`,
    first_name: name.split(" ")[0],
    last_name: name.split(" ")[1] ?? "",
    full_name: name,
    role,
    designation: "Role holder",
    department: "Registry",
    category: "academic",
    grade: "G",
    appointment_date: "2020-01-01",
    is_active: true,
  supervisor: null,
  };
}

const employees: Employee[] = [
  makeEmployee(3, "dean", "Jane Dean"),
  makeEmployee(5, "hod", "Bob HOD"),
  makeEmployee(8, "employee", "Sam Staff"),
];

describe("DelegationForm", () => {
  beforeEach(() => {
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
    user = userEvent.setup();
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
    render(<DelegationForm employees={employees} />);

    await openSelect(screen.getByLabelText("Approver"), { user });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([
      "Select the approver",
      "Jane Dean",
      "Bob HOD",
    ]);
  });

  it("submits the create shape with delegate and reason", async () => {
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });
    await selectOption(screen.getByLabelText("Delegate nomination"), "Bob HOD", {
      user,
    });
    pickDateRange(
      screen.getByLabelText("Period"),
      "2026-10-01",
      "2026-11-01"
    );
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
      ends_on: "2026-11-01",
      request_reason: "Attending a conference",
    });
  });

  it("sends null when no delegate nomination or end date is chosen", async () => {
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });
    pickRangeStart(screen.getByLabelText("Period"), "2026-10-01");

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
    render(<DelegationForm employees={employees} />);

    await selectOption(screen.getByLabelText("Approver"), "Jane Dean", { user });

    await openSelect(screen.getByLabelText("Delegate nomination"), { user });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([
      "No nomination",
      "Bob HOD",
    ]);
  });

  it("provides a cancel link back to the delegations index", () => {
    render(<DelegationForm employees={employees} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/delegations"
    );
  });
});