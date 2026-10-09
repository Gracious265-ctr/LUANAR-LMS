import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Who may be assigned to a workflow as a normal member of this team.
 *
 * `workflow` in the query string scopes the answer to one of the team's own
 * chains: its current members return as already-selected and people on other
 * chains as assigned elsewhere. Without it the answer is "everybody on the
 * team who is not already on one of our chains", which is what the
 * create-workflow screen needs.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { searchParams } = new URL(request.url);
  const workflow = searchParams.get("workflow");
  const query = workflow ? `?workflow=${encodeURIComponent(workflow)}` : "";
  return apiFetch("GET", `teams/${id}/workflow-member-pool/${query}`);
}