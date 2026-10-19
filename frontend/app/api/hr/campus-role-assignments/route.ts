import { apiFetch } from "@/app/api/_lib/api-fetch";

/** Read the campus-wide holdings, so a step form can scope and fill its roles. */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  return apiFetch(
    "GET",
    query ? `campus-role-assignments/?${query}` : "campus-role-assignments/"
  );
}

/** Appoint one person to hold a role across a whole campus. */
export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "campus-role-assignments/", { body });
}
