import { ReviewSummaryClient } from "./ReviewSummaryClient";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * The review step is a stage of the compose overlay. This route stays available
 * as a standalone page for direct links; the sidebar and list open the overlay
 * at `?edit=<id>&stage=review` instead.
 */
export default async function ReviewLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <FadeIn>
      <div className="max-w-2xl mx-auto">
        <ReviewSummaryClient applicationId={id} />
      </div>
    </FadeIn>
  );
}
