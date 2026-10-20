/**
 * Who may do what with a team, from the screens' point of view.
 *
 * The server is the authority: every predicate here mirrors a permission the
 * API enforces by refusing the other side outright. The screens offer these so
 * they do not present an action the server will 403 — a manager is not shown
 * HR's lifecycle controls, and HR is not shown the roster and step staffing
 * that were handed to the team's manager. Reading a team stays shared.
 *
 * The split mirrors the backend exactly:
 * - HR owns the team's identity, lifecycle, wide-role holdings, and which of
 *   its chains routes (`TeamViewSet.create/update`, lifecycle actions, team
 *   role assignments).
 * - The designated manager owns the team's roster, its step approvers, and the
 *   chains themselves (`TeamViewSet` members actions, `SectionMemberViewSet`,
 *   `WorkflowViewSet.create/update`).
 */

export type TeamTab = "overview" | "steps" | "approvers" | "members";

const HR_TABS: TeamTab[] = ["overview", "approvers"];
const MANAGER_TABS: TeamTab[] = ["overview", "steps", "members"];

/** The tabs a user may open on a team, from whether they are HR. */
export function visibleTeamTabs(isHr: boolean): TeamTab[] {
  return isHr ? HR_TABS : MANAGER_TABS;
}

/** Whether the user builds and edits the team's chains (the manager). */
export function canConfigureChains(isHr: boolean): boolean {
  return !isHr;
}

/** Whether the user decides which chain the team routes (HR). */
export function canRouteTeam(isHr: boolean): boolean {
  return !isHr;
}
