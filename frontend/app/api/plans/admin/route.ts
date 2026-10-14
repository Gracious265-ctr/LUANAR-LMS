import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const status = url.searchParams.get("status") ?? "";
  const blockStatus = url.searchParams.get("block_status") ?? "";
  const page = url.searchParams.get("page") ?? "1";

  const query = new URLSearchParams({ page });
  if (status) query.set("status", status);
  if (blockStatus) query.set("block_status", blockStatus);

  return apiFetch("GET", `plans/admin/?${query.toString()}`);
}
