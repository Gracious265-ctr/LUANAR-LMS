import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RoleAssignmentForm } from "@/components/hr/role-assignment-form";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import { createRoleAssignment } from "@/lib/approver-roles-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return { ...actual, createRoleAssignment: vi.fn() };
});

function makeRole(overrides: Partial<ApproverRole> = {}): ApproverRole {
  return {
    id: 2,
    code: "registrar",
    label: "Registrar",
    description: "",
    is_active: true,
    history_scope: "all",
    handles_cancellation: false,
    is_institution_wide: true,
    is_in_use: false,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeAssignment(
  overrides: Partial<RoleAssignment> = {}
): RoleAssignment {
  return {
    id: 7,
    user: 3,
    user_name: "Jane Dean",
    role: 2,
    role_label: "Registrar",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const employees = [
  makeEmployee({ id: 1, user_id: 3, full_name: "Jane Dean" }),
  makeEmployee({ id: 2, user_id: 4, full_name: "Bob Bursar" }),
  makeEmployee({ id: 3, user_id: 5, full_name: "Rita Registrar" }),
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RoleAssignmentForm", () => {
  it("offers every active employee who does not already hold the role", () => {
    render(
      <RoleAssignmentForm
        role={makeRole()}
        employees={employees}
        assignments={[makeAssignment()]}
      />
    );

    const select = screen.getByLabelText("Add a holder of Registrar");
    const names = Array.from(
      (select as HTMLSelectElement).options
    ).map((option) => option.textContent);

    expect(names).toEqual([
      "Choose a person…",
      "Bob Bursar",
      "Rita Registrar",
    ]);
  });

  it("grants the role to the chosen person and refreshes", async () => {
    vi.mocked(createRoleAssignment).mockResolvedValue(makeAssignment());
    render(<RoleAssignmentForm role={makeRole()} employees={employees} />);

    fireEvent.change(screen.getByLabelText("Add a holder of Registrar"), {
      target: { value: "4" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add holder" }));

    await waitFor(() =>
      expect(createRoleAssignment).toHaveBeenCalledWith({ user: 4, role: 2 })
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("still offers somebody whose only holding is the same code on a team", () => {
    // `approver_roles` is an aggregate over team membership and
    // institution-wide grants, so it cannot say which of the two a person
    // already has. The assignments are the authority on that.
    render(
      <RoleAssignmentForm
        role={makeRole()}
        employees={[
          makeEmployee({ id: 1, user_id: 3, approver_roles: ["registrar"] }),
        ]}
        assignments={[]}
      />
    );

    expect(
      screen.getByRole("option", { name: "Test Employee" })
    ).toBeInTheDocument();
  });

  it("hides a team role, which the Teams page staffs instead", () => {
    const { container } = render(
      <RoleAssignmentForm
        role={makeRole({ is_institution_wide: false })}
        employees={employees}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("hides a retired role, which receives no applications", () => {
    const { container } = render(
      <RoleAssignmentForm
        role={makeRole({ is_active: false })}
        employees={employees}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("never offers an inactive employee", () => {
    render(
      <RoleAssignmentForm
        role={makeRole()}
        employees={[
          makeEmployee({ id: 1, user_id: 3, is_active: false }),
          makeEmployee({ id: 2, user_id: 4, full_name: "Bob Bursar" }),
        ]}
      />
    );

    expect(
      screen.queryByRole("option", { name: "Test Employee" })
    ).not.toBeInTheDocument();
  });

  it("says every active employee already holds the role", () => {
    render(
      <RoleAssignmentForm
        role={makeRole()}
        employees={employees}
        assignments={[
          makeAssignment({ id: 7, user: 3 }),
          makeAssignment({ id: 8, user: 4 }),
          makeAssignment({ id: 9, user: 5 }),
        ]}
      />
    );

    expect(
      screen.getByText("Every active employee already holds this role.")
    ).toBeInTheDocument();
  });

  it("says there is nobody to grant the role to", () => {
    render(
      <RoleAssignmentForm
        role={makeRole()}
        employees={[makeEmployee({ id: 1, user_id: 3, is_active: false })]}
      />
    );

    expect(
      screen.getByText("No active employees are available.")
    ).toBeInTheDocument();
  });

  it("refuses to submit without a person", () => {
    render(<RoleAssignmentForm role={makeRole()} employees={employees} />);

    fireEvent.click(screen.getByRole("button", { name: "Add holder" }));

    expect(createRoleAssignment).not.toHaveBeenCalled();
    expect(
      screen.getByText("Choose somebody to hold this role.")
    ).toBeInTheDocument();
  });

  it("shows why the backend refused the grant", async () => {
    vi.mocked(createRoleAssignment).mockRejectedValue(
      new Error("That person already holds this role.")
    );
    render(<RoleAssignmentForm role={makeRole()} employees={employees} />);

    fireEvent.change(screen.getByLabelText("Add a holder of Registrar"), {
      target: { value: "4" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add holder" }));

    expect(
      await screen.findByText("That person already holds this role.")
    ).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });
});
