import { redirect } from "next/navigation";

/**
 * The leave module lands on the applicant's applications list, which is its
 * primary surface. New applications and drafts are reached from the module
 * sidebar.
 */
export default function LeaveIndexPage() {
  redirect("/leave/drafts");
}
