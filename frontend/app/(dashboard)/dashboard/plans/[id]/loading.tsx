import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

export default function PlanDetailLoading() {
  return (
    <SkeletonRegion label="Loading the plan">
      <Skeleton className="h-40 w-full max-w-2xl rounded-xl" />
    </SkeletonRegion>
  );
}
