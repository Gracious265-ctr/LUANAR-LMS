import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Read or change a team's roster.
 *
 * GET is the team members screen's data: every employee whose team is this one,
 * with the workflow they are a normal member of and whether they also staff a
 * step or hold a team-wide role. POST places one employee onto the team, with
 * the refusals the roster needs (already belongs, must be a valid employee)
 * coming back as field errors a picker can show next to its input.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("GET", `teams/${id}/members/`);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("POST", `teams/${id}/members/`, { body });
}