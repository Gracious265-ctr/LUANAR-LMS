import { redirect } from "next/navigation";

import { PlanDetail } from "@/components/plans/PlanDetail";
import { apiClient } from "@/lib/api-client";
import type { LeavePlan } from "@/lib/plans/types";

/**
 * The emailed deep link, `/plans/{id}` (spec 2.8 / 4.6).
 *
 * Server-rendered so ownership is checked before any client code runs, and so a
 * plan that is still upcoming (no reminder yet) simply reads as "not yet
 * actionable" rather than bouncing. A converted plan hands off to its draft via
 * the same component rather than redirecting on GET, since a redirect would
 * perform the conversion as a side effect of loading a page.
 */
export default async function PlanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let plan: LeavePlan;
  try {
    plan = await apiClient<LeavePlan>(`/api/v1/plans/${id}/`);
  } catch {
    // Wrong id, or a plan that is not the caller's — either way there is
    // nothing to show, so fall back to the list rather than a dead page.
    redirect("/dashboard/plans");
  }

  return <PlanDetail plan={plan} />;
}
