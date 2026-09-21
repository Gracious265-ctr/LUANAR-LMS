import { SubmittedClient } from "./SubmittedClient";

export default async function SubmittedLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="max-w-2xl mx-auto">
      <SubmittedClient applicationId={id} />
    </div>
  );
}