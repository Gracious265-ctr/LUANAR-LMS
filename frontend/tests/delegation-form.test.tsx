import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { DelegationForm } from "@/components/hr/delegation-form";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";

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
// special role: that is the shape the picker now has to cope with. The user ids
// deliberately differ from the record ids, because the form writes user ids and
// a fixture where the two coincided would hide a mix-up.
const employees: Employee[] = [
  makeEmployee({
    id: 3,
    user_id: 30,
    full_name: "Jane Dean",
    approver_roles: ["dean"],
  }),
  makeEmployee({
    id: 5,
    user_id: 50,
    full_name: "Bob HOD",
    approver_roles: ["hod"],
  }),
  makeEmployee({ id: 8, user_id: 60, full_name: "Sam Staff", approver_roles: [] }),
];

describe("DelegationForm", () => {
  beforeEach(() => {
    vi.mocked(createDelegation).mockResolvedValue({
      id: 1,
      approver: 30,
      approver_name: "Jane Dean",
      approver_role: "dean",
      delegate: 50,
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

  it("renders the delegation request fields", () => {
    render(<DelegationForm employees={employees} />);

    expect(screen.getByLabelText("Approver")).toBeInTheDocument();
    expect(screen.getByLabelText("Delegate nomination")).toBeInTheDocument();
    expect(screen.getByLabelText("Starts on")).toBeInTheDocument();
    expect(screen.getByLabelText("Ends on")).toBeInTheDocument();
    expect(screen.getByLabelText("Request reason")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create delegation request" })
    ).toBeInTheDocument();
  });

  it("only offers users with an approver role as options", () => {
    render(<DelegationForm employees={employees} />);

    const approver = screen.getByLabelText("Approver");
    const options = Array.from(approver.querySelectorAll("option")).map(
      (option) => option.textContent
    );
    expect(options).toEqual([
      "Select the approver",
      "Jane Dean",
      "Bob HOD",
    ]);
  });

  it("submits the create shape with delegate and reason", () => {
    render(<DelegationForm employees={employees} />);

    fireEvent.change(screen.getByLabelText("Approver"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText("Delegate nomination"), {
      target: { value: "50" },
    });
    fireEvent.change(screen.getByLabelText("Starts on"), {
      target: { value: "2026-10-01" },
    });
    fireEvent.change(screen.getByLabelText("Ends on"), {
      target: { value: "2026-11-01" },
    });
    fireEvent.change(screen.getByLabelText("Request reason"), {
      target: { value: "Attending a conference" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Create delegation request" })
    );

    expect(createDelegation).toHaveBeenCalledWith({
      approver: 30,
      delegate: 50,
      starts_on: "2026-10-01",
      ends_on: "2026-11-01",
      request_reason: "Attending a conference",
    });
  });

  it("sends null when no delegate nomination or end date is chosen", () => {
    render(<DelegationForm employees={employees} />);

    fireEvent.change(screen.getByLabelText("Approver"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText("Starts on"), {
      target: { value: "2026-10-01" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Create delegation request" })
    );

    expect(createDelegation).toHaveBeenCalledWith({
      approver: 30,
      delegate: null,
      starts_on: "2026-10-01",
      ends_on: null,
      request_reason: "",
    });
  });

  it("drops the nominated approver from the delegate list", () => {
    render(<DelegationForm employees={employees} />);

    fireEvent.change(screen.getByLabelText("Approver"), {
      target: { value: "30" },
    });

    const delegate = screen.getByLabelText("Delegate nomination");
    const options = Array.from(delegate.querySelectorAll("option")).map(
      (option) => option.textContent
    );
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