import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string; blockId: string }> }
) {
  const { id, blockId } = await params;
  return apiFetch("POST", `plans/${id}/blocks/${blockId}/confirm/`, { body: {} });
}