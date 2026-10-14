import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("PATCH", `approver-roles/${id}/`, { body });
}

// Retires the role rather than deleting it. The backend answers 409 with a
// sentence naming every workflow, team, and holder still using it.
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("DELETE", `approver-roles/${id}/`);
}
