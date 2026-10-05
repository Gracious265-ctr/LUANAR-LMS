import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET() {
  return apiFetch("GET", "leave-types/");
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "leave-types/", { body });
}