import { proxyRequest } from "../_lib/proxy";

export async function GET() {
<<<<<<< HEAD
  return proxyRequest("GET", "leave/my/leave-types/");
=======
  return proxyRequest("GET", "employee/leave-types/");
>>>>>>> feature/plans-teams
}