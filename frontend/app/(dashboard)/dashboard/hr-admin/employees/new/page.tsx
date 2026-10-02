import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Create now happens in an overlay on the list page, so this route only exists
 * to keep the old `new` link working: bookmarks, and anything already pointing
 * here.
 *
 * The auth and role guard is kept rather than redirecting blind, so a non-HR
 * user following one of these still lands on `/dashboard` instead of bouncing
 * through a list page that would refuse them anyway.
 */
export default async function ShimPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  redirect("/dashboard/hr-admin/employees?employee=new");
}