import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("POST", `plans/${id}/submit/`);
}
