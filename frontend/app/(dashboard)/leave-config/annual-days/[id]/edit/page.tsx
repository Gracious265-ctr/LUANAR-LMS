import { redirect } from "next/navigation";

import { requireLeaveConfigAccess } from "@/lib/leave-config-server";

/**
 * Keep `/leave-config/annual-days/<id>/edit` working: editing happens in the
 * overlay on the list page, but a bookmarked or hand-typed URL still opens it.
 */
export default async function ShimPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireLeaveConfigAccess();
  const { id } = await params;
  redirect(`/leave-config/annual-days?entitlement=${id}`);
}
