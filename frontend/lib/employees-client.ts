import { apiErrorMessage } from "./utils";

/**
 * Put somebody on a team, or take them off it.
 *
 * The team is where their leave routes, so this is the only field changed: a
 * roster move must not quietly rewrite the rest of the person's profile.
 */
export async function assignEmployeeTeam(
  id: number | string,
  team: number | null
): Promise<void> {
  const response = await fetch(`/api/hr/employees/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ team }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
}
