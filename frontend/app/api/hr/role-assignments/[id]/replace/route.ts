import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json().catch(() => ({}));
  return apiFetch("POST", `role-assignments/${id}/replace/`, { body });
}
