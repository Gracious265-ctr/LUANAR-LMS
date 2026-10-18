import { redirect } from "next/navigation";

/**
 * Editing happens in the compose overlay. This redirect keeps the old
 * `/dashboard/leave/{id}/edit` links (application cards, review pages,
 * bookmarked URLs) pointing at the right application.
 */
export default async function EditLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/dashboard/leave/drafts?edit=${id}`);
}
