import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Create and edit now happen in an overlay on the list page, so this route only
 * exists to keep the old `new` links working: any bookmarks, and the list page's
 * own "Create HR user" link before it was converted.
 *
 * The superuser guard is kept rather than redirecting blind, so a non-superuser
 * following one of these still lands on `/dashboard` instead of bouncing through
 * a list page that would refuse them anyway.
 */
export default async function ShimPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!user.is_superuser) {
    redirect("/dashboard");
  }

  redirect("/dashboard/admin/users?user=new");
}
