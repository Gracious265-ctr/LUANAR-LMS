import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const unitId = url.searchParams.get("unit_id");
  const month = url.searchParams.get("month");
  if (unitId) params.set("unit_id", unitId);
  if (month) params.set("month", month);
  return apiFetch("GET", `calendar/team/?${params.toString()}`);
}
