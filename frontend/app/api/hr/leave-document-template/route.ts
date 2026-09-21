import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function PATCH(request: Request) {
  const body = await request.json();
  return apiFetch("PATCH", "leave-document-template/", { body });
}