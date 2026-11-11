import { describe, expect, it } from "vitest";

import type {
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import { wideHoldingFrom } from "@/lib/wide-holdings";

/**
 * The panel offers "Make manager" or "Remove as manager" from
 * `holding.is_team_manager`. If the mapping from an API assignment drops that
 * flag, the write still succeeds but the screen keeps offering to make the same
 * person manager again — a button that looks broken. These lock the flag to the
 * mapping so it cannot be lost at one page and kept at another.
 */

const teamAssignment: TeamRoleAssignment = {
  id: 78,
  team: 4,
  role: 1,
  user: 3,
  user_name: "Jane Dean",
  role_label: "Supervisor",
  is_team_manager: true,
  created_at: "2026-01-01T00:00:00Z",
};

const institutionAssignment: RoleAssignment = {
  id: 77,
  role: 9,
  user: 3,
  user_name: "Jane Dean",
  role_label: "Registrar",
  created_at: "2026-01-01T00:00:00Z",
};

const campusAssignment: CampusRoleAssignment = {
  id: 79,
  campus: 2,
  role: 5,
  user: 3,
  user_name: "Jane Dean",
  role_label: "Campus Registrar",
  created_at: "2026-01-01T00:00:00Z",
};

describe("wideHoldingFrom", () => {
  it("carries the manager designation on a team-wide holding", () => {
    expect(wideHoldingFrom(teamAssignment)).toEqual({
      id: 78,
      role: 1,
      user: 3,
      user_name: "Jane Dean",
      role_label: "Supervisor",
      is_team_manager: true,
    });
  });

  it("keeps a team-wide holding that is not the manager unstyled", () => {
    expect(
      wideHoldingFrom({ ...teamAssignment, is_team_manager: false })
    ).toMatchObject({ is_team_manager: false });
  });

  it("does not invent a manager flag for an institution-wide holding", () => {
    // There is no team to manage at this scope, so the panel must not draw the
    // control; the field stays absent rather than defaulting to false.
    expect(wideHoldingFrom(institutionAssignment)).not.toHaveProperty(
      "is_team_manager"
    );
  });

  it("does not invent a manager flag for a campus-wide holding", () => {
    expect(wideHoldingFrom(campusAssignment)).not.toHaveProperty(
      "is_team_manager"
    );
  });

  it("copies the identity fields the panel renders", () => {
    expect(wideHoldingFrom(campusAssignment)).toMatchObject({
      id: 79,
      role: 5,
      user: 3,
      user_name: "Jane Dean",
      role_label: "Campus Registrar",
    });
  });
});
