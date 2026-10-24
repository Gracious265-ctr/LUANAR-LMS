import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST() {
  return apiFetch("POST", "notifications/mark-all-read/");
}
