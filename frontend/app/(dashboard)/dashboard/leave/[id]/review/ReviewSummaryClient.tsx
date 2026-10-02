"use client";

import { useRouter } from "next/navigation";

import { LeaveReviewPanel } from "@/components/leave/LeaveReviewPanel";

/**
 * Standalone review page. The compose overlay renders the same `LeaveReviewPanel`,
 * so both stay in step; this only supplies the navigation the overlay replaces.
 */
export function ReviewSummaryClient({ applicationId }: { applicationId: string }) {
  const router = useRouter();

  return (
    <LeaveReviewPanel
      applicationId={applicationId}
      onSubmitted={(id) => router.push(`/dashboard/leave/${id}/submitted`)}
    />
  );
}
