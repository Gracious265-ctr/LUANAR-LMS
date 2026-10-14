import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Take one team member off a workflow's normal-member pool.
 *
 * The pair is team + workflow on purpose: a normal member is a person on a
 * chain, so removing them needs the chain they sit on, not just the person.
 */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; userId: string }> }
) {
  const { id, userId } = await params;
  return apiFetch("DELETE", `workflows/${id}/members/${userId}/`);
}