import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET() {
  return apiFetch("GET", "plans/pending-confirmations/");
}