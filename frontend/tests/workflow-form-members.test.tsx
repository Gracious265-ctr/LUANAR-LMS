import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowForm } from "@/components/hr/workflow-form";
import { makeTeam } from "@/lib/teams/__fixtures__";
import type { WorkflowMemberPool } from "@/lib/team-members";
import { getWorkflowMemberPool } from "@/lib/team-members-client";
import { listRoleAssignments } from "@/lib/approver-roles-client";
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
    is_active: true,
    state: "standby",
    is_routing: false,
    section_count: 1,
    sections: [],
    members: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listEligibleApprovers).mockResolvedValue([]);
  vi.mocked(listRoleAssignments).mockResolvedValue([]);
});

describe("WorkflowForm members section", () => {
  it("loads the eligibility pool and offers addable team members", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());

    render(
      <WorkflowForm team={team} roles={roles} />
    );

    expect(screen.getByText(/Loading who may join/)).toBeInTheDocument();

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
              user: 31,
              full_name: "Ruth Member",
              email: "ruth@test.luanar",
              team: 4,
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

    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({ members: [31], team: 4 })
      )
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
      screen.getByText("Locked to the institution-wide holder of this role.")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

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