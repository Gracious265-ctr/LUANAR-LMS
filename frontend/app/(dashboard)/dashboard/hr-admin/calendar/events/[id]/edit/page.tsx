import { redirect } from "next/navigation";

import { requireCalendarAccess } from "@/lib/financial-years";

/**
 * Create and edit happen in an overlay on the list page, so this route only
 * exists to keep `new` / `[id]/edit` links working, including bookmarked ones.
 */
export default async function ShimPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  await requireCalendarAccess();

  redirect(`/dashboard/hr-admin/calendar?tab=holidays&event=${id}`);
}
