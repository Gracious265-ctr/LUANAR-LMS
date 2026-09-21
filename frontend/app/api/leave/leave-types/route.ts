import { proxyRequest } from "../_lib/proxy";

export async function GET() {
  return proxyRequest("GET", "employee/leave-types/");
}