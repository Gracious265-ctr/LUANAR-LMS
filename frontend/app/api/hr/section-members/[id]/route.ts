import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("DELETE", `section-members/${id}/`);
}
