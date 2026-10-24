import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("PATCH", `calendar/financial-years/${id}/`, { body });
}

// Refused with 409 while an entitlement or plan still references the period.
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("DELETE", `calendar/financial-years/${id}/`);
}
