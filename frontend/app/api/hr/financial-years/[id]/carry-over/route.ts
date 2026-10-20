import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Proxied rather than implemented here: the rule about which rejected days are
 * eligible and how much is carried belongs to the backend service, so the
 * browser cannot compute a different number from this route than the
 * management command would.
 */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("POST", `financial-years/${id}/carry-over/`);
}
