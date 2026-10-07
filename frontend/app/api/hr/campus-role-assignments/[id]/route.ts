import { apiFetch } from "@/app/api/_lib/api-fetch";

/** Drop a campus-wide holding. The role itself is untouched. */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("DELETE", `campus-role-assignments/${id}/`);
}
