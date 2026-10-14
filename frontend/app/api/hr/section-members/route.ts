import { apiFetch } from "@/app/api/_lib/api-fetch";

/** The filters the backend documents; anything else is not forwarded. */
const FILTERS = ["section", "workflow", "user"] as const;

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = FILTERS.filter((key) => params.get(key))
    .map((key) => `${key}=${encodeURIComponent(params.get(key) as string)}`)
    .join("&");
  return apiFetch(
    "GET",
    query ? `section-members/?${query}` : "section-members/"
  );
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "section-members/", { body });
}
