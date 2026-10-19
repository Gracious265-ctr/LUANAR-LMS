import { FormPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <FormPageSkeleton
      label="Loading new leave application"
      titleWidth="w-56"
      withBack={false}
    />
  );
}
