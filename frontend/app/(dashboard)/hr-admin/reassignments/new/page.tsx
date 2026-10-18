import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Reassigning now happens in an overlay on the queue, so this route only
 * exists to keep the old `reassignments/new?application=` links working: the
 * pending table's row links, and any bookmarked URL.
 *
 * The HR guard is kept rather than redirecting blind, so a non-HR user
 * following one of these still lands on `/dashboard` instead of bouncing
 * through a list page that would refuse them anyway. A missing application id
 * still means "no record selected", so it goes to the plain queue — the same
 * answer the original page gave.
 */
export default async function ShimPage({
  searchParams,
}: {
  searchParams: Promise<{ application?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/");
  }

  const params = await searchParams;
  const applicationId =
    typeof params.application === "string" ? params.application : "";

  if (!applicationId) {
    redirect("/hr-admin/reassignments");
  }

  redirect(
    `/hr-admin/reassignments?reassign=${encodeURIComponent(applicationId)}`
  );
}
