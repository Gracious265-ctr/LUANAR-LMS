import { PlanDetailView } from "@/components/plans/plan-detail";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * One plan, from the owner's side of the read.
 *
 * The component resolves the id, the access scope and what the owner may do
 * next from the API answer rather than from the route, so an approver who opens
 * this URL sees the same plan without a second code path.
 */
export default async function PlanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <FadeIn>
      <PlanDetailView id={id} />
    </FadeIn>
  );
}
