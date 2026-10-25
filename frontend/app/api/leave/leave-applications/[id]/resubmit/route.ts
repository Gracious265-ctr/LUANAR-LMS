import { proxyRequest } from "../../../_lib/proxy";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRequest("POST", `leave-applications/${id}/resubmit/`);
}
