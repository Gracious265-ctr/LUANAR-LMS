import { ListPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return (
    <ListPageSkeleton
      label="Loading leave types"
      titleWidth="w-56"
      subtitleWidth="w-96"
      columns={7}
      withSearch={false}
    />
  );
}
