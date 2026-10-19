import { redirect } from "next/navigation";

/**
 * The confirmation is the final stage of the compose overlay. This route stays
 * available as a standalone page for direct links.
 */
export default async function SubmittedLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/leave?edit=${id}&stage=done`);
}
