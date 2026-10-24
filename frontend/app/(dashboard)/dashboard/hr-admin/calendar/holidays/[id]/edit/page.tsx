import { redirect } from "next/navigation";

import { requireCalendarAccess } from "@/lib/financial-years";

/**
 * Create and edit now happen in an overlay on the list page, so this route only
 * exists to keep the old `new` / `[id]/edit` links working: the tables' row
 * links, the pencil fallback, and any bookmarked URL.
 *
 * The auth and role guard is kept rather than redirecting blind, so a
 * non-HR user following one of these still lands on `/dashboard` instead of
 * bouncing through a list page that would refuse them anyway.
 */
export default async function ShimPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  await requireCalendarAccess();

  redirect(`/dashboard/hr-admin/calendar?tab=holidays&holiday=${id}`);
}
