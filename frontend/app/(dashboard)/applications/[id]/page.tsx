import { TrackingView } from "@/components/tracking/TrackingView";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function ApplicationTrackingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <FadeIn>
      <TrackingView applicationId={id} />
    </FadeIn>
  );
}