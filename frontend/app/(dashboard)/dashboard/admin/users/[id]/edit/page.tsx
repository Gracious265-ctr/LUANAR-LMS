import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Create and edit now happen in an overlay on the list page, so this route only
 * exists to keep the old `users/<id>/edit` links working: the table's row links
 * and any bookmarked URL.
 *
 * The superuser guard is kept rather than redirecting blind, so a non-superuser
 * following one of these still lands on `/dashboard` instead of bouncing through
 * a list page that would refuse them anyway. The id is passed through as-is; if
 * it no longer matches an account the overlay says so rather than the list page
 * refusing the request.
 */
export default async function ShimPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!user.is_superuser) {
    redirect("/dashboard");
  }

  const { id } = await params;
  redirect(`/dashboard/admin/users?user=${encodeURIComponent(id)}`);
}
