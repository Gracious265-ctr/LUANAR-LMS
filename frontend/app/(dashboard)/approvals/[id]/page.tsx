import { ApprovalReview } from "@/components/approvals/approval-review";

export default async function ApprovalReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-5xl">
      <ApprovalReview applicationId={id} />
    </div>
  );
}