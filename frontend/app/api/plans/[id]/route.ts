import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("GET", `plans/${id}/`);
}
