import { ApprovalReview } from "@/components/approvals/approval-review";

export default async function ApprovalReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ cancellation?: string | string[] }>;
}) {
  const [{ id }, sp] = await Promise.all([params, searchParams]);
  const cancellation =
    typeof sp.cancellation === "string" ? sp.cancellation : undefined;
  return (
    <div className="mx-auto max-w-5xl">
      <ApprovalReview
        applicationId={id}
        cancellationRequestId={cancellation}
      />
    </div>
  );
}