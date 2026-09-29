import { apiFetch } from "@/app/api/_lib/api-fetch";

const ALLOWED_SCOPES = new Set(["mine", "team", "department", "all"]);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const scope = url.searchParams.get("scope") ?? "mine";
  const query = new URLSearchParams({ scope: ALLOWED_SCOPES.has(scope) ? scope : "mine" });
  return apiFetch("GET", `plans/?${query.toString()}`);
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "plans/", { body });
}