import { FormPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <FormPageSkeleton
      label="Loading the leave type"
      titleWidth="w-48"
      withBack={false}
    />
  );
}
