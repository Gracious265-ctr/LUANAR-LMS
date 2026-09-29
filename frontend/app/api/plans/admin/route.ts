import { apiFetch } from "@/app/api/_lib/api-fetch";

const ALLOWED_PLAN_STATUSES = new Set(["draft", "submitted", "approved", "rejected"]);
const ALLOWED_BLOCK_STATUSES = new Set([
  "proposed",
  "reserved",
  "confirmed",
  "lapsed",
  "released",
]);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const status = url.searchParams.get("status") ?? "";
  const blockStatus = url.searchParams.get("block_status") ?? "";
  const page = url.searchParams.get("page") ?? "1";

  const query = new URLSearchParams({ page });
  if (ALLOWED_PLAN_STATUSES.has(status)) query.set("status", status);
  if (ALLOWED_BLOCK_STATUSES.has(blockStatus)) query.set("block_status", blockStatus);
  return apiFetch("GET", `plans/admin/?${query.toString()}`);
}