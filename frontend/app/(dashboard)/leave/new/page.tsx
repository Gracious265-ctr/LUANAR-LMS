import { redirect } from "next/navigation";

/**
 * The apply flow is now an overlay on the applications list, so this route
 * only exists to keep the sidebar's "New Application" link and any bookmarked
 * URL working.
 */
export default async function NewLeavePage() {
  redirect("/leave/drafts?compose=1");
}
