import type {
  Campus,
  Team,
  TeamMember,
  TeamSectionMember,
} from "@/lib/teams";

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
    department: "",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    status: "draft",
    effective_from: null,
    effective_to: null,
    is_effective: false,
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "hod", label: "Head of Department" },
    ],
    member_count: 0,
    members: [],
    sections: [
      {
        id: 1,
        name: "Direct supervisor",
        order: 1,
        is_active: true,
        approver_role: "supervisor",
        approver_role_label: "Supervisor",
        member_count: 0,
        members: [],
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

/**
 * One person's period on one step, as the API reports it. A membership is a
 * period, so the fixture always has to say when it starts and — for a closed
 * one — when it ended.
 */
export function makeSectionMember(
  overrides: Partial<TeamSectionMember> = {}
): TeamSectionMember {
  return {
    id: 11,
    user: 3,
    user_name: "Jane Dean",
    user_email: "jane.dean@test.luanar",
    effective_from: "2026-01-01",
    effective_to: null,
    is_effective: true,
    ...overrides,
  };
}
