import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET() {
  return apiFetch("GET", "admin-users/");
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "admin-users/", { body });
}
