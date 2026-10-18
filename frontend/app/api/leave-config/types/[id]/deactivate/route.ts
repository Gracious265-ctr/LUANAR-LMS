import { apiFetch } from "@/app/api/_lib/api-fetch";

/** POST only — deactivation is the confirm-gated retirement of §1.5. */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  return apiFetch("POST", `leave-config/types/${id}/deactivate/`);
}
