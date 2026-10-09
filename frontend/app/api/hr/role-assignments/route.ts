import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  return apiFetch("GET", query ? `role-assignments/?${query}` : "role-assignments/");
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "role-assignments/", { body });
}
