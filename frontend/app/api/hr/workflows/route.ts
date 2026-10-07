import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Create a chain for a team.
 *
 * The team is required and checked on the backend: a chain belongs to the team
 * it was created for, and there is no such thing as a chain that belongs to
 * nobody — no employee's application could ever reach it.
 */
export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "workflows/", { body });
}
