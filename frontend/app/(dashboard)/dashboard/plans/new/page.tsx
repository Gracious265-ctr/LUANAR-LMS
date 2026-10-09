import { redirect } from "next/navigation";

/**
 * Create now happens in an overlay on the workspace, so this route only exists
 * to keep the old `plans/new` links working: any bookmarks, and the workspace's
 * own "New plan" link before it was converted.
 *
 * No guard is kept because the original page never had one — the list page
 * itself is what decides who may plan, and it still does.
 */
export default async function ShimPage() {
  redirect("/dashboard/plans?plan=new");
}
