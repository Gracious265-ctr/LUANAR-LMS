import { proxyRequest } from "../_lib/proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const status = url.searchParams.get("status");
  const path = status
    ? `leave-applications/?status=${encodeURIComponent(status)}`
    : "leave-applications/";
  return proxyRequest("GET", path);
}

export async function POST(request: Request) {
  const body = await request.json();
  return proxyRequest("POST", "leave-applications/", body);
}
