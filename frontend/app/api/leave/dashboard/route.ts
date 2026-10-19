import { proxyRequest } from "../_lib/proxy";

export async function GET() {
  return proxyRequest("GET", "leave/dashboard/");
}
