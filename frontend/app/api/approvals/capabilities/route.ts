<<<<<<< HEAD
import { proxyRequest } from "../../leave/_lib/proxy";

export async function GET() {
  return proxyRequest("GET", `approvals/capabilities/`);
=======
import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET() {
  return apiFetch("GET", "approvals/capabilities/");
>>>>>>> feature/plans-teams
}