import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ReassignmentForm } from "@/components/hr/reassignment-form";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { PendingApplication } from "@/lib/reassignments";
import { openSelect, selectOption } from "./helpers/select";

vi.mock("@/lib/reassignments-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/reassignments-client")>();
  return {
    ...actual,
    reassignApplication: vi.fn(),
  };
});

import { reassignApplication } from "@/lib/reassignments-client";

// The approvers here hold their positions as data, and their accounts carry no
// special role: that is the shape the pickers now have to cope with. User ids
// differ from record ids, because the form writes user ids.
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

const application: PendingApplication = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 60,
  employee_name: "Sam Staff",
  leave_type_name: "Annual",
  start_date: "2026-10-01",
  end_date: "2026-10-05",
  calculated_days: 5,
  reason: "Family visit",
  submitted_at: "2026-09-18T10:00:00Z",
  current_approver: null,
  current_approver_name: "",
  acting_approver: null,
  acting_approver_name: "",
  is_delegated: false,
};

describe("ReassignmentForm", () => {
  beforeEach(() => {
    vi.mocked(reassignApplication).mockResolvedValue({
      id: 1,
      application: "app-1",
      reference_number: "LUANAR-2026-0001",
      employee: 8,
      employee_name: "Sam Staff",
      from_approver: null,
      from_approver_name: "",
      to_approver: 30,
      to_approver_name: "Jane Dean",
      reason: "Urgent case",
      decided_by: 1,
      decided_by_name: "Aisha HR",
      created_at: "2026-09-18T12:00:00Z",
    });
  });

  it("renders the application summary, approver select, and mandatory reason", () => {
    render(<ReassignmentForm application={application} employees={employees} />);

    expect(
      screen.getByText("LUANAR-2026-0001 — Sam Staff (Annual)")
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Replacement approver")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Reassignment reason")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reassign application" })
    ).toBeInTheDocument();
  });

  it("marks the reason textarea as required", () => {
    render(<ReassignmentForm application={application} employees={employees} />);

    expect(
      screen.getByLabelText("Reassignment reason")
    ).toHaveAttribute("required");
  });

  it("offers approver-role users except the applicant", async () => {
    const user = userEvent.setup();
    render(<ReassignmentForm application={application} employees={employees} />);

    await openSelect(screen.getByLabelText("Replacement approver"), { user });

    expect(
      screen.getAllByRole("option").map((option) => option.textContent)
    ).toEqual(["Select the replacement approver", "Jane Dean", "Bob HOD"]);
  });

  it("warns when the current approver is away and their delegate is acting", () => {
    /* The cover overlay is applied at query time, so reassigning back to the
       named approver would leave their delegate acting. Stated before submit. */
    render(
      <ReassignmentForm
        employees={employees}
        application={{
          ...application,
          current_approver: 30,
          current_approver_name: "Jane Dean",
          acting_approver: 50,
          acting_approver_name: "Bob HOD",
          is_delegated: true,
        }}
      />
    );

    expect(
      screen.getByText(/Bob HOD is currently acting as delegate for Jane Dean/)
    ).toBeInTheDocument();
  });

  it("shows no cover warning when nobody is delegating", () => {
    render(
      <ReassignmentForm
        employees={employees}
        application={{
          ...application,
          current_approver: 30,
          current_approver_name: "Jane Dean",
          acting_approver: 30,
          acting_approver_name: "Jane Dean",
        }}
      />
    );

    expect(screen.queryByText(/acting as delegate/)).not.toBeInTheDocument();
  });

  it("excludes the current approver from the options", async () => {
    const user = userEvent.setup();
    render(
      <ReassignmentForm
        application={{ ...application, current_approver: 30, current_approver_name: "Jane Dean" }}
        employees={employees}
      />
    );

    await openSelect(screen.getByLabelText("Replacement approver"), { user });

    expect(
      screen.getAllByRole("option").map((option) => option.textContent)
    ).toEqual(["Select the replacement approver", "Bob HOD"]);
  });

  it("submits the reassign shape with application, to_approver, and reason", async () => {
    const user = userEvent.setup();
    render(<ReassignmentForm application={application} employees={employees} />);

    await selectOption(
      screen.getByLabelText("Replacement approver"),
      "Jane Dean",
      { user }
    );
    fireEvent.change(screen.getByLabelText("Reassignment reason"), {
      target: { value: "Urgent case" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Reassign application" })
    );

    expect(reassignApplication).toHaveBeenCalledWith({
      application: "app-1",
      to_approver: 30,
      reason: "Urgent case",
    });
  });

  it("shows backend errors and keeps the form", async () => {
    vi.mocked(reassignApplication).mockRejectedValue(
      new Error("to_approver: The application is already assigned to this approver.")
    );
    const user = userEvent.setup();
    render(<ReassignmentForm application={application} employees={employees} />);

    await selectOption(
      screen.getByLabelText("Replacement approver"),
      "Jane Dean",
      { user }
    );
    fireEvent.change(screen.getByLabelText("Reassignment reason"), {
      target: { value: "Try again" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Reassign application" })
    );

    expect(
      await screen.findByText(
        "to_approver: The application is already assigned to this approver."
      )
    ).toBeInTheDocument();
  });

  it("provides a cancel link back to the reassignments index", () => {
    render(<ReassignmentForm application={application} employees={employees} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/hr-admin/reassignments"
    );
  });
});