import { proxyRequest } from "../../leave/_lib/proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const search = url.search ? url.search : "";
  return proxyRequest("GET", `approvals/cancellations/${search}`);
}