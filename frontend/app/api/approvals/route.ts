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
}