import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import type { Campus, Team } from "@/lib/teams";
import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { createTeam, updateTeam } from "@/lib/teams-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return {
    ...actual,
    createTeam: vi.fn(),
    updateTeam: vi.fn(),
  };
});

const campuses: Campus[] = [
  makeCampus(),
  makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" }),
];

const roles: ApproverRole[] = [
  {
    id: 1,
    code: "supervisor",
    label: "Supervisor",
    description: "",
    is_active: true,
    history_scope: "team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: true,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    code: "lead",
    label: "Team Leader",
    description: "",
    is_active: true,
    history_scope: "team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: true,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

/** An employee as the manager picker reads them. */
function makeEmployee(overrides: Partial<Employee> = {}): Employee {
  return {
    id: 3,
    user_id: 3,
    email: "jane.dean@test.luanar",
    first_name: "Jane",
    last_name: "Dean",
    full_name: "Jane Dean",
    role: "employee",
    approver_roles: [],
    designation: "Dean",
    category: "administration",
    grade: "",
    appointment_date: null,
    team: null,
    team_name: "",
    is_active: true,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

/**
 * A team being edited. Administration by default: these tests are about the
 * details and the manager step, and an academic team with no campus is refused.
 */
function existingTeam(overrides: Partial<Team> = {}): Team {
  return makeTeam({
    name: "Registry",
    description: "",
    category: "administration",
    campus: null,
    status: "active",
    is_effective: true,
    sections: [],
    ...overrides,
  });
}

describe("TeamForm", () => {
  it("creates a team through the two-step wizard, sending the manager picked on the second step", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // Page one asks only what the team is. Nothing is written until the manager
    // step is finished.
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(createTeam).not.toHaveBeenCalled();

    // Page two names the manager: a team-scoped role and a category-matching
    // employee who holds no wide approver role.
    fireEvent.change(screen.getByLabelText("Manager role"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Manager"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Registry",
          manager: { role: 1, user: 3 },
        })
      )
    );
    // The team's chain is the manager's to build and route, so the form sends
    // none of it.
    const input = vi.mocked(createTeam).mock.calls[0][0];
    expect(input).not.toHaveProperty("new_workflow");
    expect(input).not.toHaveProperty("workflow");
    expect(push).toHaveBeenCalledWith("/organisation/teams/4");
    expect(refresh).toHaveBeenCalled();
  });

  it("offers only active employees of the team's category who hold no wide approver role", async () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[
          makeEmployee({ user_id: 3, full_name: "Jane Dean" }),
          makeEmployee({
            user_id: 4,
            full_name: "Ada Academic",
            category: "academic",
          }),
          makeEmployee({ user_id: 5, full_name: "Wendy Wide" }),
          makeEmployee({ user_id: 6, full_name: "Ida Inactive", is_active: false }),
        ]}
        wideHolderUserIds={[5]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const person = screen.getByLabelText("Manager");

    expect(within(person).getByRole("option", { name: "Jane Dean" })).toBeInTheDocument();
    expect(
      within(person).queryByRole("option", { name: "Ada Academic" })
    ).not.toBeInTheDocument();
    expect(
      within(person).queryByRole("option", { name: "Wendy Wide" })
    ).not.toBeInTheDocument();
    expect(
      within(person).queryByRole("option", { name: "Ida Inactive" })
    ).not.toBeInTheDocument();
  });

  it("refuses to save without a manager role", async () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    expect(
      await screen.findByText(/Choose the team-scoped role the manager will hold/)
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("refuses to save without a manager", async () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Manager role"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    expect(
      await screen.findByText(/Choose who will manage this team/)
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("refuses an academic team with no campus before reaching the manager step", async () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("radio", { name: /academic/i }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(
      await screen.findByText(/An academic team sits at a campus/i)
    ).toBeInTheDocument();
    // Still on page one: the manager step was never reached.
    expect(
      screen.queryByRole("button", { name: "Save team" })
    ).not.toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("sends the chosen campus as an id, and only for an academic team", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[
          makeEmployee({ user_id: 3, category: "academic", full_name: "Jane Dean" }),
        ]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // The campus select is the visible half of the rule: it is disabled until
    // the team is said to be academic, because an administration team does not
    // sit at a campus at all.
    expect(screen.getByLabelText("Campus")).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /academic/i }));
    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Manager role"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Manager"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          campus: 1,
          category: "academic",
          manager: { role: 1, user: 3 },
        })
      )
    );
  });

  it("sends an administration team with no campus, as institution-wide", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // The default category is administration, and the campus is cleared rather
    // than left at whatever an earlier screen might have held.
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Manager role"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Manager"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "administration",
          campus: null,
        })
      )
    );
  });

  it("saves an edit's details only, with no manager step and no chain", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={existingTeam()}
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    // An edit has no second page: the manager is changed on the Approvers tab
    // and the chain is the manager's own screen.
    expect(
      screen.queryByRole("button", { name: "Next" })
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ name: "Registry renamed" })
      )
    );
    const input = vi.mocked(updateTeam).mock.calls[0][1];
    expect(input).not.toHaveProperty("manager");
    expect(input).not.toHaveProperty("new_workflow");
    expect(input).not.toHaveProperty("workflow");
    expect(push).toHaveBeenCalledWith("/organisation/teams/4");
  });

  it("says so when the roles could not be loaded, rather than offering a blank picker", () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={[]}
        employees={[makeEmployee()]}
        rolesError="Unable to load approver roles. Please try again."
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(
      screen.getByText("Unable to load approver roles. Please try again.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Manager role")).toBeDisabled();
  });

  it("shows why the backend refused the team and stays on the form", async () => {
    vi.mocked(createTeam).mockRejectedValue(
      new Error("A team with that name already exists.")
    );
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[makeEmployee()]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Manager role"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Manager"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save team" }));

    expect(
      await screen.findByText("A team with that name already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
