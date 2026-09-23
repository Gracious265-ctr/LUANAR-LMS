import { proxyRequest } from "../../leave/_lib/proxy";

export async function GET() {
  return proxyRequest("GET", `approvals/capabilities/`);
}