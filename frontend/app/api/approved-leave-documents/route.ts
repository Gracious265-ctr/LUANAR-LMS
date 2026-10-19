import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * The documents module's approved-document feed: every generated approved
 * leave document whose application belongs to the caller, newest first.
 */
export async function GET() {
  return apiFetch("GET", "approved-leave-documents/");
}
