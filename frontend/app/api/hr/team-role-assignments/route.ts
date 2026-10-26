import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  return apiFetch(
    "GET",
    query ? `team-role-assignments/?${query}` : "team-role-assignments/"
  );
}

/** Appoint one person to hold a role across a whole team. */
export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "team-role-assignments/", { body });
}
