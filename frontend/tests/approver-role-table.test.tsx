import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ApproverRoleTable } from "@/components/hr/approver-role-table";
import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  deactivateApproverRole,
  removeCampusRoleAssignment,
  removeRoleAssignment,
  removeTeamRoleAssignment,
} from "@/lib/approver-roles-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return {
    ...actual,
    deactivateApproverRole: vi.fn(),
    removeRoleAssignment: vi.fn(),
    removeTeamRoleAssignment: vi.fn(),
    removeCampusRoleAssignment: vi.fn(),
  };
});

function makeRole(overrides: Partial<ApproverRole> = {}): ApproverRole {
  return {
    id: 1,
    code: "lead",
    label: "Team Leader",
    description: "",
    is_active: true,
    history_scope: "same_team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: false,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ApproverRoleTable", () => {
  it("renders an empty state when no roles exist", () => {
    render(<ApproverRoleTable roles={[]} assignments={{}} />);

    expect(screen.getByText("No roles found")).toBeInTheDocument();
  });

  it("lists roles with their code, history scope, and kind", () => {
    render(
      <ApproverRoleTable
        roles={[
          makeRole(),
          makeRole({
            id: 2,
            code: "registrar",
            label: "Registrar",
            history_scope: "all",
            is_institution_wide: true,
          }),
        ]}
        assignments={{}}
      />
    );

    expect(screen.getByText("Team Leader")).toBeInTheDocument();
    expect(screen.getByText("lead")).toBeInTheDocument();
    expect(screen.getByText("Same team only")).toBeInTheDocument();
    expect(screen.getByText("Team role")).toBeInTheDocument();
    expect(screen.getByText("Registrar")).toBeInTheDocument();
    expect(screen.getByText("Full history")).toBeInTheDocument();
    expect(screen.getByText("Institution-wide")).toBeInTheDocument();
  });

  it("falls back to the stored value for a history scope it does not know", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ history_scope: "same_college" })]}
        assignments={{}}
      />
    );

    // A scope added to the backend after this build must still read.
    expect(screen.getByText("same_college")).toBeInTheDocument();
  });

  it("lists what is using a role, so the blocker is visible", () => {
    render(
      <ApproverRoleTable
        roles={[
          makeRole({
            is_in_use: true,
            usage: ["Used by workflow: Academic approval", "Team: Bunda Faculty"],
          }),
        ]}
        assignments={{}}
      />
    );

    expect(
      screen.getByText("Used by workflow: Academic approval")
    ).toBeInTheDocument();
    expect(screen.getByText("Team: Bunda Faculty")).toBeInTheDocument();
  });

  it("says a retired role is retired instead of offering to retire it again", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ is_active: false })]}
        assignments={{}}
      />
    );

    expect(screen.getByText("Retired")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retire" })).not.toBeInTheDocument();
  });

  it("retires a role through DELETE and refreshes", async () => {
    vi.mocked(deactivateApproverRole).mockResolvedValue(
      makeRole({ is_active: false })
    );
    render(<ApproverRoleTable roles={[makeRole()]} assignments={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() => expect(deactivateApproverRole).toHaveBeenCalledWith(1));
    expect(refresh).toHaveBeenCalled();
  });

  it("shows the backend's refusal when a role is still in use", async () => {
    vi.mocked(deactivateApproverRole).mockRejectedValue(
      new Error('role: "Team Leader" is still used by 1 workflow.')
    );
    render(<ApproverRoleTable roles={[makeRole()]} assignments={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    expect(
      await screen.findByText(
        'role: "Team Leader" is still used by 1 workflow.'
      )
    ).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("warns when an institution-wide role has no holder", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ is_institution_wide: true })]}
        assignments={{}}
      />
    );

    expect(
      screen.getByText(
        "No holder — applications reaching this role have nobody to approve"
      )
    ).toBeInTheDocument();
  });

  it("does not warn about a retired institution-wide role having no holder", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ is_institution_wide: true, is_active: false })]}
        assignments={{}}
      />
    );

    expect(
      screen.getByText("Retired — no longer routes applications")
    ).toBeInTheDocument();
    expect(screen.queryByText(/nobody to approve/)).not.toBeInTheDocument();
  });

  it("says it could not load the holders instead of claiming there is none", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ is_institution_wide: true })]}
        assignments={undefined}
      />
    );

    expect(screen.getByText("Could not load the holders")).toBeInTheDocument();
    expect(screen.queryByText(/nobody to approve/)).not.toBeInTheDocument();
  });

  it("links each row to the role editor", () => {
    render(
      <ApproverRoleTable
        roles={[makeRole({ id: 2 })]}
        assignments={{}}
      />
    );

    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/roles/2/edit"
    );
  });

  it("says a team role is staffed through membership when nobody holds it wide", () => {
    render(<ApproverRoleTable roles={[makeRole()]} assignments={{}} />);

    expect(screen.getByText("Team role")).toBeInTheDocument();
    expect(
      screen.getByText("Staffed through team membership")
    ).toBeInTheDocument();
  });

  it("reads a role with a team-wide holder as team-wide by that holder", async () => {
    const assignment: TeamRoleAssignment = {
      id: 8,
      team: 9,
      role: 1,
      user: 3,
      user_name: "Sam Supervisor",
      role_label: "Supervisor",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(removeTeamRoleAssignment).mockResolvedValue(undefined);
    render(
      <ApproverRoleTable
        roles={[makeRole()]}
        assignments={{}}
        teamHoldings={{ 1: [assignment] }}
        teamNameById={{ 9: "ICT Team" }}
      />
    );

    expect(screen.getByText("Team-wide")).toBeInTheDocument();
    expect(screen.queryByText("Team role")).not.toBeInTheDocument();
    expect(screen.getByText("Sam Supervisor — ICT Team")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Sam Supervisor from the ICT Team team",
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() => expect(removeTeamRoleAssignment).toHaveBeenCalledWith(8));
    expect(refresh).toHaveBeenCalled();
  });

  it("reads a role with a campus-wide holder as campus-wide by that holder", async () => {
    const assignment: CampusRoleAssignment = {
      id: 2,
      campus: 4,
      role: 1,
      user: 3,
      user_name: "Cas Campus",
      role_label: "Campus Registrar",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(removeCampusRoleAssignment).mockResolvedValue(undefined);
    render(
      <ApproverRoleTable
        roles={[makeRole()]}
        assignments={{}}
        campusHoldings={{ 1: [assignment] }}
        campusNameById={{ 4: "Bunda Campus" }}
      />
    );

    expect(screen.getByText("Campus-wide")).toBeInTheDocument();
    expect(screen.getByText("Cas Campus — Bunda Campus")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Cas Campus from the Bunda Campus campus",
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() =>
      expect(removeCampusRoleAssignment).toHaveBeenCalledWith(2)
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("names an institution-wide holder and removes them", async () => {
    const assignment: RoleAssignment = {
      id: 7,
      user: 3,
      user_name: "Jane Dean",
      role: 2,
      role_label: "Registrar",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(removeRoleAssignment).mockResolvedValue(undefined);
    render(
      <ApproverRoleTable
        roles={[makeRole({ id: 2, is_institution_wide: true })]}
        assignments={{ 2: [assignment] }}
      />
    );

    expect(screen.getByText("Jane Dean")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Remove Jane Dean from this role" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() => expect(removeRoleAssignment).toHaveBeenCalledWith(7));
    expect(refresh).toHaveBeenCalled();
  });
});
