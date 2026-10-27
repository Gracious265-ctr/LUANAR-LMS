import type { Campus, Team, TeamMember } from "@/lib/teams";

/** A campus as the API reports it. */
export function makeCampus(overrides: Partial<Campus> = {}): Campus {
  return {
    id: 1,
    name: "Main Campus",
    code: "main",
    description: "",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/**
 * A team as the API reports it. Members are derived from the workflow's
 * sections, so the flattening on a team row lists each person with the
 * sections they sit on.
 */
export function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 4,
    name: "Bunda College Faculty",
    code: "bunda-faculty",
    description: "",
    category: "academic",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    workflows: [
      {
        id: 1,
        name: "Academic approval",
        is_routing: true,
        section_count: 1,
        effective_from: null,
        is_active: true,
      },
    ],
    status: "draft",
    effective_from: null,
    effective_to: null,
    is_effective: false,
    is_team_manager: false,
    manager_user: null,
    manager_name: "",
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "lead", label: "Team Leader" },
    ],
    member_count: 0,
    roster_count: 0,
    members: [],
    sections: [
      {
        id: 1,
        name: "Direct supervisor",
        order: 1,
        is_active: true,
        approver_role: "supervisor",
        approver_role_label: "Supervisor",
        resolution: "staffed",
        approver: null,
      },
    ],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/**
 * A flattened team-member row as the API reports it: the person, the sections
 * they can act for, and the roles those sections ask for.
 */
export function makeTeamMember(overrides: Partial<TeamMember> = {}): TeamMember {
  return {
    user: 3,
    user_name: "Jane Dean",
    user_email: "jane.dean@test.luanar",
    sections: [{ id: 1, name: "Direct supervisor", order: 1 }],
    roles: [{ id: 1, code: "supervisor", label: "Supervisor" }],
    ...overrides,
  };
}


