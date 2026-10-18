import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = {
  title: "Review application",
};

export default async function ApprovalDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ cancellation?: string | string[] }>;
}) {
  const { id } = await params;
  const { cancellation } = await searchParams;
  const cancellationRequestId = Array.isArray(cancellation)
    ? cancellation[0]
    : cancellation;
  return (
    <FadeIn>
      <ApprovalDetail
        id={id}
        cancellationRequestId={cancellationRequestId ?? undefined}
      />
    </FadeIn>
  );
}