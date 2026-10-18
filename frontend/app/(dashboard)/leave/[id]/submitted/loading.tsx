import { FormPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <FormPageSkeleton
      label="Loading application submitted"
      titleWidth="w-56"
      withBack={false}
    />
  );
}
