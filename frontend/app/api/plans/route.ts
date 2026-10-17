import { proxyRequest } from "./_lib/proxy";

export async function GET() {
  return proxyRequest("GET", "plans/");
}

export async function POST(request: Request) {
  const body = await request.json();
  return proxyRequest("POST", "plans/", body);
}
