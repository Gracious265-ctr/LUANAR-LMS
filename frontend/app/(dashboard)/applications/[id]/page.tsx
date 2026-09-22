import { TrackingView } from "@/components/tracking/TrackingView";

export default async function ApplicationTrackingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TrackingView applicationId={id} />;
}