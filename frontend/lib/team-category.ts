/**
 * Which kind of team this is, in a module that never touches the server.
 *
 * `lib/teams.ts` reads Django through `api-client.ts`, which uses `cookies`
 * from `next/headers` and is therefore a server-only module. A client
 * component that imported the category labels from there would put
 * `next/headers` into the browser bundle and fail to compile. Everything a
 * client screen needs to *say* about a team's category lives here, and the
 * server module re-exports it so server callers keep one import path.
 */

/**
 * An academic team sits at a campus, so its stages may resolve to a campus-wide
 * holder. An administration team is institution-wide, so its stages are the
 * only ones an institution-wide approver may serve. The two are exclusive, and
 * the campus relationship is the visible half of the rule: "this team sits at a
 * campus" is exactly "this team is academic".
 */
export type TeamCategory = "academic" | "administration";

export const TEAM_CATEGORY_LABELS: Record<TeamCategory, string> = {
  academic: "Academic",
  administration: "Administration",
};

export const TEAM_CATEGORY_CODES: TeamCategory[] = [
  "academic",
  "administration",
];

export function teamCategoryLabel(category: string): string {
  return TEAM_CATEGORY_LABELS[category as TeamCategory] ?? category;
}

/**
 * The `Badge` `tone` for a category, so a caller renders the shared pill
 * rather than restating the class string.
 */
export function teamCategoryBadgeTone(
  category: string
): "brand" | "muted" {
  return category === "academic" ? "brand" : "muted";
}
