import { apiFetch } from "@/app/api/_lib/api-fetch";

/** The filter the backend documents; anything else is not forwarded. */
const FILTERS = ["department", "role"] as const;

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = FILTERS.filter((key) => params.get(key))
    .map((key) => `${key}=${encodeURIComponent(params.get(key) as string)}`)
    .join("&");
  return apiFetch(
    "GET",
    query ? `teams/eligible-approvers/?${query}` : "teams/eligible-approvers/"
  );
}