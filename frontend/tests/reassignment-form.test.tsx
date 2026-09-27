import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ReassignmentForm } from "@/components/hr/reassignment-form";
import type { Employee, UserRole } from "@/lib/employees";
import type { PendingApplication } from "@/lib/reassignments";

vi.mock("@/lib/reassignments-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/reassignments-client")>();
  return {
    ...actual,
    reassignApplication: vi.fn(),
  };
});

import { reassignApplication } from "@/lib/reassignments-client";

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
  };
}

const employees: Employee[] = [
  makeEmployee(3, "dean", "Jane Dean"),
  makeEmployee(5, "hod", "Bob HOD"),
  makeEmployee(8, "employee", "Sam Staff"),
];

const application: PendingApplication = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
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
      to_approver: 3,
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

  it("offers approver-role users except the applicant", () => {
    render(<ReassignmentForm application={application} employees={employees} />);

    const select = screen.getByLabelText("Replacement approver");
    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.textContent
    );
    expect(options).toEqual([
      "Select the replacement approver",
      "Jane Dean",
      "Bob HOD",
    ]);
  });

  it("warns when the current approver is away and their delegate is acting", () => {
    /* The cover overlay is applied at query time, so reassigning back to the
       named approver would leave their delegate acting. Stated before submit. */
    render(
      <ReassignmentForm
        employees={employees}
        application={{
          ...application,
          current_approver: 3,
          current_approver_name: "Jane Dean",
          acting_approver: 5,
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
          current_approver: 3,
          current_approver_name: "Jane Dean",
          acting_approver: 3,
          acting_approver_name: "Jane Dean",
        }}
      />
    );

    expect(screen.queryByText(/acting as delegate/)).not.toBeInTheDocument();
  });

  it("excludes the current approver from the options", () => {
    render(
      <ReassignmentForm
        application={{ ...application, current_approver: 3, current_approver_name: "Jane Dean" }}
        employees={employees}
      />
    );

    const select = screen.getByLabelText("Replacement approver");
    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.textContent
    );
    expect(options).toEqual(["Select the replacement approver", "Bob HOD"]);
  });

  it("submits the reassign shape with application, to_approver, and reason", () => {
    render(<ReassignmentForm application={application} employees={employees} />);

    fireEvent.change(screen.getByLabelText("Replacement approver"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText("Reassignment reason"), {
      target: { value: "Urgent case" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Reassign application" })
    );

    expect(reassignApplication).toHaveBeenCalledWith({
      application: "app-1",
      to_approver: 3,
      reason: "Urgent case",
    });
  });

  it("shows backend errors and keeps the form", async () => {
    vi.mocked(reassignApplication).mockRejectedValue(
      new Error("to_approver: The application is already assigned to this approver.")
    );
    render(<ReassignmentForm application={application} employees={employees} />);

    fireEvent.change(screen.getByLabelText("Replacement approver"), {
      target: { value: "3" },
    });
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
      "/dashboard/hr-admin/reassignments"
    );
  });
});