import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const tab = url.searchParams.get("tab") ?? "pending";
  const page = url.searchParams.get("page") ?? "1";

  const query = new URLSearchParams({ tab, page });
  return apiFetch("GET", `approvals/cancellations/?${query.toString()}`);
}