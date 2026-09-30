import { apiFetch } from "@/app/api/_lib/api-fetch";

const SCOPES = new Set(["mine", "team", "department", "all"]);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const requested = url.searchParams.get("scope") ?? "mine";
  // The API falls back to `mine` for anything it does not know; narrowing here
  // keeps a hand-edited URL from silently showing the caller's own plans under
  // a team or department heading.
  const scope = SCOPES.has(requested) ? requested : "mine";

  return apiFetch("GET", `plans/?scope=${scope}`);
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "plans/", { body });
}
