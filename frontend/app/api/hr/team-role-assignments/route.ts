import { apiFetch } from "@/app/api/_lib/api-fetch";

/** Appoint one person to hold a role across a whole team. */
export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "team-role-assignments/", { body });
}
