<<<<<<< HEAD
import { proxyRequest } from "../leave/_lib/proxy";

const ALLOWED = new Set(["tab", "q", "page", "page_size"]);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const qs = new URLSearchParams();
  for (const [key, value] of searchParams) {
    if (ALLOWED.has(key) && value) qs.set(key, value);
  }
  const query = qs.toString();
  return proxyRequest("GET", `approvals/${query ? `?${query}` : ""}`);
=======
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
>>>>>>> feature/plans-teams
}