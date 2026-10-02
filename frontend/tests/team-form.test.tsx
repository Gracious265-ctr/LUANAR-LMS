import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Department } from "@/lib/departments";
import type { Campus, EligibleApprover, TeamSection } from "@/lib/teams";
import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import {
  createTeam,
  listEligibleApprovers,
  updateTeam,
} from "@/lib/teams-client";
import { createDepartment } from "@/lib/departments-client";
import { createApproverRole } from "@/lib/approver-roles-client";

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
    listEligibleApprovers: vi.fn(),
  };
});

vi.mock("@/lib/departments-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/departments-client")>();
  return { ...actual, createDepartment: vi.fn() };
});

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return { ...actual, createApproverRole: vi.fn() };
});

const campuses: Campus[] = [
  makeCampus(),
  makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" }),
];

const departments: Department[] = [
  {
    id: 1,
    name: "Bunda College",
    is_active: true,
    team_count: 0,
    employee_count: 2,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Administration",
    is_active: true,
    team_count: 0,
    employee_count: 1,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
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
    code: "hod",
    label: "Head of Department",
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

const jane: EligibleApprover = {
  id: 3,
  full_name: "Jane Dean",
  email: "jane.dean@test.luanar",
  designation: "Dean",
};
const bob: EligibleApprover = {
  id: 5,
  full_name: "Bob HOD",
  email: "bob.hod@test.luanar",
  designation: "Head of Department",
};

/** A step as the API reports it, so tests do not restate the flattened fields. */
function makeSection(overrides: Partial<TeamSection> = {}): TeamSection {
  return { ...makeTeam().sections[0], ...overrides };
}

function mockCandidates(byRole: Record<number, EligibleApprover[]>) {
  vi.mocked(listEligibleApprovers).mockImplementation(
    async (_department: number, role?: number) =>
      role === undefined ? [] : byRole[role] ?? []
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockCandidates({ 1: [jane], 2: [bob] });
});

/** Fills page one and moves to page two. */
function openSteps(overrides: { department?: string; name?: string } = {}) {
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: overrides.name ?? "Registry" },
  });
  fireEvent.change(screen.getByLabelText("Department"), {
    target: { value: overrides.department ?? "1" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Continue to approval steps" })
  );
}

/** The step at `position` (1-based, as it is labelled on screen). */
function step(position: number) {
  return within(screen.getByRole("group", { name: `Step ${position}` }));
}

describe("TeamForm", () => {
  it("asks for the team's identity before its chain, and saves nothing on the way", () => {
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to approval steps" })
    );

    expect(
      screen.getByRole("heading", { name: "Who approves for this team" })
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
    expect(updateTeam).not.toHaveBeenCalled();
  });

  it("names each step after the role it uses, so nothing is typed for it", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();

    // HR only picks a role and a person: there is no box to name the step and
    // no box to name the chain, so the two cannot drift from the role or from
    // each other between two people configuring the same team.
    expect(screen.queryByLabelText("Chain name")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(step(1).queryByLabelText("Step 1 name")).toBeNull();
    await waitFor(() =>
      expect(listEligibleApprovers).toHaveBeenCalledWith(1, 1)
    );
    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 2 role"), {
      target: { value: "hod" },
    });
    await waitFor(() =>
      expect(step(2).getByRole("option", { name: /Bob HOD/ })).toBeInTheDocument()
    );
    fireEvent.change(step(2).getByLabelText("Step 2 approver"), {
      target: { value: "5" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Registry",
          department: 1,
          new_workflow: {
            sections: [
              {
                name: "Supervisor",
                approver_role: "supervisor",
                approver: 3,
              },
              {
                name: "Head of Department",
                approver_role: "hod",
                approver: 5,
              },
            ],
          },
        })
      )
    );
    // No chain name is sent: the backend names a new chain after the team and
    // keeps the existing one on an edit.
    expect(
      vi.mocked(createTeam).mock.calls[0][0].new_workflow
    ).not.toHaveProperty("name");
    expect(vi.mocked(createTeam).mock.calls[0][0]).not.toHaveProperty("workflow");
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/teams");
    expect(refresh).toHaveBeenCalled();
  });

  it("saves a team with no steps as a draft, because a chain can be added later", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Save as draft" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Registry", department: 1 })
      )
    );
    expect(vi.mocked(createTeam).mock.calls[0][0]).not.toHaveProperty(
      "new_workflow"
    );
  });

  it("refuses to create a chain whose step names no single approver", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      await screen.findByText(
        "Name the one person who decides at every step, or save the team as a draft."
      )
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("scopes the approver picker to the department, and clears it when the role changes", async () => {
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps({ department: "1" });
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("3");

    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "hod" },
    });
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Bob HOD/ })).toBeInTheDocument()
    );
    // The person chosen for the previous role is likely not eligible for the new
    // one, so the choice is cleared rather than sent and refused.
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("");
  });

  it("cannot pick an approver before a department is chosen", () => {
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to approval steps" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    expect(step(1).getByLabelText("Step 1 approver")).toBeDisabled();
    expect(
      screen.getByText(/Choose a department first/)
    ).toBeInTheDocument();
  });

  it("prefills an existing team's details and its one approver per step", async () => {
    render(
      <TeamForm
        team={makeTeam({
          campus: 2,
          campus_name: "Bunda Campus",
          workflow: 2,
          workflow_name: "Administrative approval",
          department: 1,
          department_name: "Bunda College",
          effective_from: "2026-01-01",
          sections: [
            makeSection({
              id: 7,
              name: "Supervisor approval",
              approver_role: "supervisor",
              approver: {
                id: 3,
                user_name: "Jane Dean",
                user_email: "jane.dean@test.luanar",
              },
            }),
          ],
        })}
        campuses={campuses}
        departments={departments}
        roles={roles}
      />
    );

    // An edit opens on the steps page, because that is where the work is.
    expect(
      screen.getByRole("heading", { name: "Who approves for this team" })
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Step 1 role")).toHaveValue("supervisor");
    // The approver the step already had, once its people have been fetched.
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("3")
    );
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("sends the edited chain with its approver, so an edit does not unappoint a step", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={makeTeam({
          department: 1,
          department_name: "Bunda College",
          sections: [
            makeSection({
              name: "Supervisor approval",
              approver_role: "supervisor",
              approver: {
                id: 3,
                user_name: "Jane Dean",
                user_email: "jane.dean@test.luanar",
              },
            }),
          ],
        })}
        campuses={campuses}
        departments={departments}
        roles={roles}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          department: 1,
          new_workflow: {
            sections: [
              {
                name: "Supervisor",
                approver_role: "supervisor",
                approver: 3,
              },
            ],
          },
        })
      )
    );
    expect(createTeam).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/teams/4");
  });

  it("reorders the steps by what is shown rather than by the order they were added", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 2 role"), {
      target: { value: "hod" },
    });
    await waitFor(() =>
      expect(step(2).getByRole("option", { name: /Bob HOD/ })).toBeInTheDocument()
    );
    fireEvent.change(step(2).getByLabelText("Step 2 approver"), {
      target: { value: "5" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move step 2 up" }));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({ approver_role: "hod", approver: 5 }),
              expect.objectContaining({ approver_role: "supervisor", approver: 3 }),
            ],
          }),
        })
      )
    );
  });

  it("sends the chosen campus as an id and leaves a blank one null", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Department"), {
      target: { value: "1" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to approval steps" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Save as draft" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ campus: 1 })
      )
    );
  });

  it("says so when the departments could not be loaded", () => {
    render(
      <TeamForm
        campuses={campuses}
        departments={[]}
        roles={roles}
        departmentsError="Unable to load departments, so this team cannot be placed in one."
      />
    );

    expect(
      screen.getByText(
        "Unable to load departments, so this team cannot be placed in one."
      )
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Department")).toBeDisabled();
  });

  it("says so when the roles could not be loaded, rather than offering a blank step", () => {
    render(
      <TeamForm
        campuses={campuses}
        departments={departments}
        roles={[]}
        rolesError="Unable to load approver roles, so the approval steps cannot be described."
      />
    );

    openSteps();

    expect(
      screen.getByText(
        "Unable to load approver roles, so the approval steps cannot be described."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add step" })).toBeDisabled();
  });

  it("shows why the backend refused the team and stays on the form", async () => {
    vi.mocked(createTeam).mockRejectedValue(
      new Error("A team with that name already exists.")
    );
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Save as draft" }));

    expect(
      await screen.findByText("A team with that name already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("creates a department from the form and selects it without leaving", async () => {
    const created: Department = {
      id: 9,
      name: "ICT",
      is_active: true,
      team_count: 0,
      employee_count: 0,
      teams: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(createDepartment).mockResolvedValue(created);
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create department" }));
    fireEvent.change(screen.getByLabelText("New department name"), {
      target: { value: "ICT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save department" }));

    await waitFor(() =>
      expect(createDepartment).toHaveBeenCalledWith({ name: "ICT" })
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Department")).toHaveValue("9")
    );
    expect(screen.getByRole("option", { name: "ICT" })).toBeInTheDocument();
  });

  it("surfaces a refused department instead of silently failing", async () => {
    vi.mocked(createDepartment).mockRejectedValue(
      new Error("A department with this name already exists.")
    );
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create department" }));
    fireEvent.change(screen.getByLabelText("New department name"), {
      target: { value: "ICT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save department" }));

    expect(
      await screen.findByText("A department with this name already exists.")
    ).toBeInTheDocument();
  });

  it("creates an approver role while describing a step and offers it", async () => {
    const created: ApproverRole = {
      id: 9,
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
    };
    vi.mocked(createApproverRole).mockResolvedValue(created);
    render(
      <TeamForm campuses={campuses} departments={departments} roles={roles} />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByLabelText("New role name"), {
      target: { value: "Registrar" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save role" }));

    await waitFor(() =>
      expect(createApproverRole).toHaveBeenCalledWith({ label: "Registrar" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(screen.getByRole("option", { name: "Registrar" })).toBeInTheDocument();
  });

  it("appoints the single institution-wide holder automatically when its role is chosen", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const holder: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [holder] });
    vi.mocked(createTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        campuses={campuses}
        departments={departments}
        roles={[...roles, registrar]}
      />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "registrar" },
    });

    // Selecting the role is the instruction: the one holder is filled in
    // without HR touching the picker, which could not have offered them first.
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("11")
    );
    expect(
      screen.getByText(/Its holder approves automatically/)
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({
                name: "Registrar",
                approver_role: "registrar",
                approver: 11,
              }),
            ],
          }),
        })
      )
    );
  });

  it("appoints a step whose role was already loaded, without asking again", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const holder: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [holder] });
    vi.mocked(createTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        campuses={campuses}
        departments={departments}
        roles={[registrar, ...roles]}
      />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("11")
    );

    // A second step takes the same role. Its people were already asked for, so
    // nothing is fetched again — the step must still be appointed rather than
    // waiting on a request that will never be made.
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(2).getByLabelText("Step 2 approver")).toHaveValue("11")
    );
    expect(
      vi
        .mocked(listEligibleApprovers)
        .mock.calls.filter(([, role]) => role === 9)
    ).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({ approver_role: "registrar", approver: 11 }),
              expect.objectContaining({ approver_role: "registrar", approver: 11 }),
            ],
          }),
        })
      )
    );
  });

  it("leaves an institution-wide step to HR when several hold the role", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const first: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    const second: EligibleApprover = {
      id: 12,
      full_name: "Rex Registrar",
      email: "rex.registrar@test.luanar",
      designation: "Deputy Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [first, second] });
    vi.mocked(createTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        campuses={campuses}
        departments={departments}
        roles={[...roles, registrar]}
      />
    );

    openSteps();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "registrar" },
    });

    await waitFor(() =>
      expect(
        step(1).getByRole("option", { name: /Rita Registrar/ })
      ).toBeInTheDocument()
    );
    expect(
      step(1).getByRole("option", { name: /Rex Registrar/ })
    ).toBeInTheDocument();
    // Several holders is a real choice, so nothing is decided for HR.
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("");

    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({
                approver_role: "registrar",
                approver: 12,
              }),
            ],
          }),
        })
      )
    );
  });
});