import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * The grade ids the eligibility multi-select labels (§1.4).
 *
 * Grades are directory data, not leave-configuration data — this only mirrors
 * them so the form can label the ids stored on the type.
 */
export async function GET() {
  return apiFetch("GET", "leave-config/grades/");
}
