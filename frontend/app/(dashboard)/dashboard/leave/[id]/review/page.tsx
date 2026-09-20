import { ReviewSummaryClient } from "./ReviewSummaryClient";

export default async function ReviewLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="max-w-2xl mx-auto">
      <ReviewSummaryClient applicationId={id} />
    </div>
  );
}