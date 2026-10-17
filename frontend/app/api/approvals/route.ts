import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const tab = url.searchParams.get("tab") ?? "pending";
  const q = url.searchParams.get("q") ?? "";
  const page = url.searchParams.get("page") ?? "1";

  const query = new URLSearchParams({ tab });
  if (q) query.set("q", q);
  if (page) query.set("page", page);

  return apiFetch("GET", `approvals/?${query.toString()}`);
}