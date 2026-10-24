import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const unreadOnly = url.searchParams.get("unread_only");
  const qs = unreadOnly ? `?unread_only=${encodeURIComponent(unreadOnly)}` : "";
  return apiFetch("GET", `notifications/${qs}`);
}
