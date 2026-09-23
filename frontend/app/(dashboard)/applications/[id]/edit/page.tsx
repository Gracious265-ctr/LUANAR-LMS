import { EditApplicationContent } from "@/components/applications/resubmission/edit-application";

export default async function EditLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <EditApplicationContent applicationId={id} />;
}