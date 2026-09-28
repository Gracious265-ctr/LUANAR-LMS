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

/** A team as the API reports it, with its members and stage roles expanded. */
export function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 4,
    name: "Bunda College Faculty",
    code: "bunda-faculty",
    description: "",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    is_active: true,
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "hod", label: "Head of Department" },
    ],
    member_count: 0,
    members: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/** A team membership as the API reports it. */
export function makeTeamMember(overrides: Partial<TeamMember> = {}): TeamMember {
  return {
    id: 9,
    team: 4,
    user: 3,
    user_name: "Jane Dean",
    role: "supervisor",
    role_label: "Supervisor",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}
