import type {
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "./approver-roles";

/**
 * One holding, whatever its scope: the role, the person, and the scope it is
 * held at. The shape is the same at all three levels on purpose, so one panel
 * can render and write all three.
 */
export interface WideHolding {
  id: number;
  role: number;
  user: number;
  user_name: string;
  role_label: string;
  /**
   * The team's single designated manager, on a team-wide holding only.
   *
   * A manager is a team-wide approver who additionally runs the team's own
   * members and workflow configuration, so the flag rides the holding rather
   * than the person and is written by HR through the set-manager action. The
   * campus and institution-wide scopes never carry it — there is nothing for
   * them to manage.
   */
  is_team_manager?: boolean;
}

/**
 * Turn an assignment as the API returns it into a holding the panel can render.
 *
 * The manager designation is the one field that only a team-wide holding has,
 * and it is what tells the panel whether to offer "Make manager" or "Remove as
 * manager". Dropping it here (as the pages used to) leaves every holder looking
 * like they are not the manager: the designation is written successfully, the
 * page re-reads, and the button still offers to make them manager — a button
 * that looks broken even though the write went through.
 *
 * Kept here rather than in each page so the three scopes share one mapping and
 * the field cannot be lost at one call site and kept at another.
 */
export function wideHoldingFrom(
  assignment: RoleAssignment | TeamRoleAssignment | CampusRoleAssignment
): WideHolding {
  const holding: WideHolding = {
    id: assignment.id,
    role: assignment.role,
    user: assignment.user,
    user_name: assignment.user_name,
    role_label: assignment.role_label,
  };
  // Only a team-wide holding carries the designation; the panel reads its
  // absence as "not a manager" and draws no manager control at the other
  // scopes.
  if ("is_team_manager" in assignment) {
    holding.is_team_manager = assignment.is_team_manager;
  }
  return holding;
}
