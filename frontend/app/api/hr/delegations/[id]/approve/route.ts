import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("POST", `delegations/${id}/approve/`, { body });
}