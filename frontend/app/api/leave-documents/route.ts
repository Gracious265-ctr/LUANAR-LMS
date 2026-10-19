import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * The documents module's supporting-documents feed: every supporting document
 * attached to the caller's leave applications. ``?include_retired=true`` adds
 * the archive, mirroring the per-application list.
 */
export async function GET(request: Request) {
  const includeRetired = new URL(request.url).searchParams.get(
    "include_retired"
  );
  const path = includeRetired
    ? "leave-documents/?include_retired=true"
    : "leave-documents/";
  return apiFetch("GET", path);
}
