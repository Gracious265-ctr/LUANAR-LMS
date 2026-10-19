import { redirect } from "next/navigation";

/**
 * The review step now lives in the compose overlay, so this route only exists
 * to keep the old `leave/<id>/review` links working: bookmarks, and the draft
 * list's own links before it was converted. The overlay resumes at the same
 * stage this standalone page used to render.
 */
export default async function ReviewLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  redirect(`/leave?edit=${encodeURIComponent(id)}&stage=review`);
}
