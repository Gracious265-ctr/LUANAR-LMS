import { redirect } from "next/navigation";

import { requireLeaveConfigAccess } from "@/lib/leave-config-server";

/**
 * Keep `/leave-config/annual-days/new` working: creation happens in the overlay
 * on the list page, but a typed URL should still open the form.
 */
export default async function ShimPage() {
  await requireLeaveConfigAccess();
  redirect("/leave-config/annual-days?entitlement=new");
}
