import { redirect } from "next/navigation";

/**
 * The organisation module lands on its teams list, which is its primary
 * surface. Campuses, approver roles, and role assignments are reached from the
 * module sidebar.
 */
export default function OrganisationIndexPage() {
  redirect("/organisation/teams");
}
