import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowForm } from "@/components/hr/workflow-form";
import { makeTeam } from "@/lib/teams/__fixtures__";
import type { WorkflowMemberPool } from "@/lib/team-members";
import { getWorkflowMemberPool } from "@/lib/team-members-client";
import {
  createOrReuseApproverRole,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles-client";
import { listEligibleApprovers } from "@/lib/teams-client";
import type { EligibleApprover } from "@/lib/teams";
import type { Workflow } from "@/lib/workflows";
import { createWorkflow } from "@/lib/workflows-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/team-members-client", () => ({
  listTeamMembers: vi.fn(),
  addTeamMember: vi.fn(),
  removeTeamMember: vi.fn(),
  getWorkflowMemberPool: vi.fn(),
  removeWorkflowMember: vi.fn(),
}));

vi.mock("@/lib/workflows-client", () => ({
  createWorkflow: vi.fn(),
}));

vi.mock("@/lib/teams-client", () => ({
  listEligibleApprovers: vi.fn(),
}));

vi.mock("@/lib/approver-roles-client", () => ({
  listRoleAssignments: vi.fn(),
  listTeamRoleAssignments: vi.fn(),
  listCampusRoleAssignments: vi.fn(),
  createOrReuseApproverRole: vi.fn(),
}));

const roles = [
  {
    id: 1,
    code: "supervisor",
    label: "Supervisor",
    description: "",
    is_active: true,
    history_scope: "section" as const,
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: false,
    usage: [],
    created_at: "",
    updated_at: "",
  },
];

const team = makeTeam({ id: 4, name: "Bunda College Faculty" });

function makePool(
  overrides: Partial<WorkflowMemberPool> = {}
): WorkflowMemberPool {
  return {
    team: { id: 4, name: "Bunda College Faculty", code: "bunda-faculty" },
    workflow: null,
    available: [
      {
        id: 31,
        user: 31,
        full_name: "Ruth Member",
        email: "ruth@test.luanar",
        designation: "Lecturer",
        category: "academic",
        faculty: "Agriculture",
        grade: "G",
        is_active: true,
      },
      {
        id: 32,
        user: 32,
        full_name: "Sam Candidate",
        email: "sam@test.luanar",
        designation: "Assistant",
        category: "administration",
        faculty: "",
        grade: "A",
        is_active: true,
      },
    ],
    current: [],
    assigned_elsewhere: [],
    ...overrides,
  };
}

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: 1,
    name: "Academic approval",
    team: 4,
    team_name: "Bunda College Faculty",
    effective_from: null,
    effective_to: null,
    is_active: true,
    state: "standby",
    is_routing: false,
    section_count: 1,
    sections: [],
    members: [],
    ...overrides,
  };
}

/** A chain carries its own name; the form refuses a blank one on save. */
function fillName(value = "Academic approval") {
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
    target: { value },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listEligibleApprovers).mockResolvedValue([]);
  vi.mocked(listRoleAssignments).mockResolvedValue([]);
  vi.mocked(listTeamRoleAssignments).mockResolvedValue([]);
  vi.mocked(listCampusRoleAssignments).mockResolvedValue([]);
});

describe("WorkflowForm members section", () => {
  it("loads the eligibility pool and offers addable team members", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());

    render(
      <WorkflowForm team={team} roles={roles} />
    );

    expect(screen.getByText("Loading members...")).toBeInTheDocument();

    await screen.findByText("Ruth Member");
    expect(getWorkflowMemberPool).toHaveBeenCalledWith(4, undefined);
    expect(
      screen.getAllByRole("button", { name: "Add" }).length
    ).toBeGreaterThan(0);
  });

  it("pre-fills the current members of an edited workflow", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(
      makePool({
        workflow: { id: 1, name: "Academic approval", state: "standby", is_active: true, is_routing: false },
        current: [
          {
            id: 31,
            user: 31,
            full_name: "Ruth Member",
            email: "ruth@test.luanar",
            designation: "Lecturer",
            category: "academic",
            faculty: "Agriculture",
            grade: "G",
            is_active: true,
          },
        ],
      })
    );

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          members: [
            {
              id: 1,
              workflow: 1,
              workflow_name: "Academic approval",
              user: 31,
              user_name: "Ruth Member",
              user_email: "ruth@test.luanar",
              designation: "Lecturer",
              team: 4,
              team_name: "Bunda College Faculty",
              added_by: 1,
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        })}
      />
    );

    expect(
      await screen.findByText(/On this chain/)
    ).toBeInTheDocument();
    expect(screen.getByText("Ruth Member")).toBeInTheDocument();
    expect(getWorkflowMemberPool).toHaveBeenCalledWith(4, 1);
  });

  it("adds and removes a member and submits the chosen ids", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    await screen.findByText("Ruth Member");

    fireEvent.click(
      screen.getByRole("button", { name: "Add step" })
    );
    fireEvent.click(
      screen.getAllByRole("button", { name: "Add" })[0]
    );
    expect(screen.getByText(/On this chain/)).toBeInTheDocument();

    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({ members: [31], team: 4 })
      )
    );
    // It lands on the team's workflow list under /dashboard, which is where the
    // report actually lives: /organisation/teams/... is not a route.
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/dashboard/teams/4/workflows")
    );
  });
});

describe("WorkflowForm approver picker", () => {
  const sam: EligibleApprover = {
    id: 32,
    full_name: "Sam Candidate",
    email: "sam@test.luanar",
    designation: "Assistant",
  };
  const ruth: EligibleApprover = {
    id: 31,
    full_name: "Ruth Member",
    email: "ruth@test.luanar",
    designation: "Lecturer",
  };

  it("loads candidates scoped to the role and a new chain, and submits the chosen approver", async () => {
    vi.mocked(listEligibleApprovers).mockResolvedValue([sam, ruth]);
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByRole("combobox", { name: /approver/i });
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1, "new");

    fireEvent.change(
      screen.getByRole("combobox", { name: /approver/i }),
      { target: { value: "32" } }
    );
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: expect.arrayContaining([
            expect.objectContaining({ approver: 32 }),
          ]),
        })
      )
    );
  });

  it("pre-fills the current approver of an edited chain and scopes candidates to it", async () => {
    vi.mocked(listEligibleApprovers).mockResolvedValue([ruth]);

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          sections: [
            {
              id: 7,
              name: "Supervisor",
              order: 1,
              is_active: true,
              approver_role: "supervisor",
              approver_role_label: "Supervisor",
              approver: 31,
              approver_name: "Ruth Member",
              resolution: {
                source: "section",
                automatic: false,
                user: 31,
                user_name: "Ruth Member",
                label: "Ruth Member",
              },
              description: "",
              members: [],
              member_count: 0,
              memberships: [],
            },
          ],
        })}
      />
    );

    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1, 1);
    const select = await screen.findByRole("combobox", {
      name: /approver/i,
    });
    expect((select as HTMLSelectElement).value).toBe("31");
    expect(
      screen.getByRole("option", { name: "Ruth Member" })
    ).toBeInTheDocument();
  });
});

describe("WorkflowForm institution-wide auto-appointment", () => {
  const adminTeam = makeTeam({
    id: 4,
    name: "ICT Team",
    category: "administration",
  });

  const wideRoles = [
    ...roles,
    {
      id: 2,
      code: "registrar",
      label: "Registrar",
      description: "",
      is_active: true,
      history_scope: "section" as const,
      handles_cancellation: false,
      is_institution_wide: true,
      is_in_use: false,
      usage: [],
      created_at: "",
      updated_at: "",
    },
  ];

  const dingo = { id: 40, full_name: "Dingo Dean", email: "", designation: "" };

  it("locks the approver of an institution-wide step to its holder and submits that id", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={adminTeam} roles={wideRoles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    await screen.findByText("Dingo Dean");
    expect(
      screen.queryByText("Locked to the institution-wide holder of this role.")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: expect.arrayContaining([
            expect.objectContaining({ approver: 40 }),
          ]),
        })
      )
    );
  });

  it("leaves an institution-wide step unstaffed when no single holder exists", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
      {
        id: 10,
        user: 41,
        user_name: "Pat Principal",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);

    render(<WorkflowForm team={adminTeam} roles={wideRoles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    const select = await screen.findByRole("combobox", {
      name: "Approver",
    });
    expect((select as HTMLSelectElement).value).toBe("");
  });

  it("does not fill an institution-wide step on an academic team", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);

    render(
      <WorkflowForm
        team={makeTeam({ id: 4, category: "academic" })}
        roles={wideRoles}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    const select = await screen.findByRole("combobox", {
      name: "Approver",
    });
    expect((select as HTMLSelectElement).value).toBe("");
  });
});

describe("WorkflowForm wide approver locking", () => {
  const academicTeam = makeTeam({ id: 4, campus: 3, category: "academic" });

  function teamHolding(user: number, name: string) {
    return {
      id: 20,
      team: 4,
      role: 1,
      user,
      user_name: name,
      role_label: "Supervisor",
      is_team_manager: false,
      created_at: "",
    };
  }

  function campusHolding(user: number, name: string) {
    return {
      id: 21,
      campus: 3,
      role: 1,
      user,
      user_name: name,
      role_label: "Supervisor",
      created_at: "",
    };
  }

  it("locks a step to its team-wide holder and submits that person", async () => {
    vi.mocked(listTeamRoleAssignments).mockResolvedValue([
      teamHolding(50, "Tina Team"),
    ]);
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Tina Team");
    expect(listTeamRoleAssignments).toHaveBeenCalledWith(4);
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: 50 }],
        })
      )
    );
  });

  it("falls back to the campus-wide holder when the team has none", async () => {
    vi.mocked(listCampusRoleAssignments).mockResolvedValue([
      campusHolding(51, "Cara Campus"),
    ]);
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Cara Campus");
    expect(listCampusRoleAssignments).toHaveBeenCalledWith(3);
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: 51 }],
        })
      )
    );
  });

  it("prefers the team-wide holder over the campus-wide one", async () => {
    vi.mocked(listTeamRoleAssignments).mockResolvedValue([
      teamHolding(50, "Tina Team"),
    ]);
    vi.mocked(listCampusRoleAssignments).mockResolvedValue([
      campusHolding(51, "Cara Campus"),
    ]);

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Tina Team");
    expect(screen.queryByText("Cara Campus")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();
  });

  it("keeps the picker when the role has no wide holder", async () => {
    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await waitFor(() => expect(listTeamRoleAssignments).toHaveBeenCalled());
    expect(
      screen.getByRole("combobox", { name: "Approver" })
    ).toBeInTheDocument();
  });

  it("does not read campus holdings for a team with no campus", async () => {
    render(<WorkflowForm team={makeTeam({ campus: null })} roles={roles} />);

    await waitFor(() => expect(listTeamRoleAssignments).toHaveBeenCalled());
    expect(listCampusRoleAssignments).not.toHaveBeenCalled();
  });
});

describe("WorkflowForm repeated roles", () => {
  it("disables a role already used on another step", async () => {
    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    const secondRoleSelect = screen.getAllByRole("combobox", {
      name: "Role",
    })[1];
    const supervisorOption = screen.getByRole("option", {
      name: "Supervisor — used in step 1",
    });
    expect(supervisorOption).toBeDisabled();
    expect(
      (supervisorOption as HTMLOptionElement).value
    ).toBe("supervisor");
    expect(secondRoleSelect).toBeInTheDocument();
  });
});

describe("WorkflowForm step naming", () => {
  it("takes the step name from its role and offers no name box", async () => {
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    // There is no step-name control at all: the step is named by the role it
    // selects, and the payload carries no name.
    expect(screen.queryByText("Step name")).not.toBeInTheDocument();

    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: null }],
        })
      )
    );
  });

  it("locks an institution-wide step to its holder without a name box", async () => {
    const wideRoles = [
      ...roles,
      {
        ...roles[0],
        id: 2,
        code: "registrar",
        label: "Registrar",
        is_institution_wide: true,
      },
    ];
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([
      { id: 40, full_name: "Dingo Dean", email: "", designation: "" },
    ]);

    render(
      <WorkflowForm
        team={makeTeam({ id: 4, category: "administration" })}
        roles={wideRoles}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Role" }), {
      target: { value: "registrar" },
    });

    await screen.findByText("Dingo Dean");
    expect(screen.queryByText("Step name")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Locked to the institution-wide holder of this role.")
    ).not.toBeInTheDocument();
  });
});

describe("WorkflowForm new role card", () => {
  const createdRole = {
    ...roles[0],
    id: 9,
    code: "examinations-officer",
    label: "Examinations Officer",
  };

  it("adds a role by name and makes it selectable on a step", async () => {
    vi.mocked(createOrReuseApproverRole).mockResolvedValue({
      role: createdRole,
      created: true,
    });

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Role name" }), {
      target: { value: "Examinations Officer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    await waitFor(() =>
      expect(createOrReuseApproverRole).toHaveBeenCalledWith(
        "Examinations Officer"
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(
      await screen.findByRole("option", { name: "Examinations Officer" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Added Examinations Officer.")
    ).toBeInTheDocument();
  });

  it("reuses the existing role instead of claiming a duplicate was made", async () => {
    vi.mocked(createOrReuseApproverRole).mockResolvedValue({
      role: createdRole,
      created: false,
    });

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Role name" }), {
      target: { value: "examinations officer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    expect(
      await screen.findByText(/already exists — using it/i)
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    // Folded into the list once, not appended twice.
    expect(
      screen.getAllByRole("option", { name: "Examinations Officer" })
    ).toHaveLength(1);
  });
});