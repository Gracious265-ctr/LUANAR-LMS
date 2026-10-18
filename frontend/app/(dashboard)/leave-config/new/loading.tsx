import { FormPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <FormPageSkeleton
      label="Loading the leave type form"
      titleWidth="w-64"
      withBack={false}
    />
  );
}
