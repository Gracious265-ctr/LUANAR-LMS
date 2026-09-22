import { proxyRequest } from "../_lib/proxy";

export async function POST(request: Request) {
  const body = await request.json();
  return proxyRequest("POST", "leave/validate/", body);
}