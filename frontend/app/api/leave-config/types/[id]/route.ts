import { apiFetch } from "@/app/api/_lib/api-fetch";

/** The registry's integer primary key; anything else is not one of ours. */
function isTypeId(id: string): boolean {
  return /^\d+$/.test(id);
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  if (!isTypeId(id)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  return apiFetch("GET", `leave-config/types/${id}/`);
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  if (!isTypeId(id)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  const body = await request.json();
  return apiFetch("PATCH", `leave-config/types/${id}/`, { body });
}
