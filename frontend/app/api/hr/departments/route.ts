import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = params.get("include_retired") === "1" ? "?include_retired=1" : "";
  return apiFetch("GET", `departments/${query}`);
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "departments/", { body });
}
