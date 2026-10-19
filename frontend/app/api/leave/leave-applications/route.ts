import { proxyRequest } from "../_lib/proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const status = url.searchParams.get("status");
  if (status) params.set("status", status);
  const excludeStatus = url.searchParams.get("exclude_status");
  if (excludeStatus) params.set("exclude_status", excludeStatus);
  const query = params.toString();
  return proxyRequest(
    "GET",
    query ? `leave-applications/?${query}` : "leave-applications/"
  );
}

export async function POST(request: Request) {
  const body = await request.json();
  return proxyRequest("POST", "leave-applications/", body);
}
