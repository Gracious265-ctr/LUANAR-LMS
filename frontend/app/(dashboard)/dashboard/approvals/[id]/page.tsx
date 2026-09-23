import { ApprovalDetail } from "@/components/approvals/approval-detail";

export const metadata = {
  title: "Review application",
};

export default async function ApprovalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ApprovalDetail id={id} />;
}