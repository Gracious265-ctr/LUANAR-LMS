import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Edit a chain the owning team has.
 *
 * The team named on the body must be the chain's own team: a chain cannot be
 * adopted by another, because the applications already inside it would be
 * stranded at steps nobody staffs for them.
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("PATCH", `workflows/${id}/`, { body });
}
