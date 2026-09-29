import { FormPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <FormPageSkeleton
      label="Loading edit application"
      titleWidth="w-56"
      withBack={true}
    />
  );
}
