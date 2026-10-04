import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Create and edit now happen in an overlay on the list page, so this route only
 * exists to keep the old `new` / `[id]/edit` links working: the table's row
 * links, the pencil fallback, and any bookmarked URL.
 *
 * The auth and role guard is kept rather than redirecting blind, so a non-HR
 * user following one of these still lands on `/dashboard` instead of bouncing
 * through a list page that would refuse them anyway.
 *
 * No read happens here. The overlay resolves the department from the rows the
 * list already fetched, so a bogus id is reported by the dialog rather than
 * costing a request that would 404 here.
 */
export default async function ShimPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  redirect(`/dashboard/hr-admin/departments?department=${id}`);
}