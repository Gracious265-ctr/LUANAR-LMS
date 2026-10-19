import { proxyRequest } from "../_lib/proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const scope = url.searchParams.get("scope");
  const month = url.searchParams.get("month");
  const query = new URLSearchParams();
  if (scope) query.set("scope", scope);
  if (month) query.set("month", month);
  const qs = query.toString() ? `?${query.toString()}` : "";
  return proxyRequest("GET", `plans/team/${qs}`);
}
