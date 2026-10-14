import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Proxied rather than implemented here: the rule about what a ready team is
 * belongs to the backend, so the browser cannot get a different answer from
 * this one than the activation action itself would give.
 */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("POST", `teams/${id}/validate/`);
}
