import { PlanApprovalDetailView } from "@/components/plans/plan-approval-detail";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * One plan, from the approver's side of the read.
 *
 * The approver read carries `responsible_approver_id` and `decision_version`,
 * which the owner read does not, so it is a separate route rather than a
 * variant of the detail page.
 */
export default async function PlanApprovalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <FadeIn>
      <PlanApprovalDetailView id={id} />
    </FadeIn>
  );
}
