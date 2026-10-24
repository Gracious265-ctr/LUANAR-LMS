import { redirect } from "next/navigation";

import { requireCalendarAccess } from "@/lib/financial-years";

/**
 * Create and edit happen in an overlay on the list page, so this route only
 * exists to keep `new` / `[id]/edit` links working, including bookmarked ones.
 */
export default async function ShimPage() {
  await requireCalendarAccess();

  redirect("/dashboard/hr-admin/calendar?tab=holidays&event=new");
}
