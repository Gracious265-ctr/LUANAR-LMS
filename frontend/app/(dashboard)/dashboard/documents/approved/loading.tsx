import { ListPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return <ListPageSkeleton label="Loading approved documents" columns={6} withAction={false} />
}
