import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST() {
  return apiFetch("POST", "setup/rollover/", { body: {} });
}
