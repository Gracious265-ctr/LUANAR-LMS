import { ListPageSkeleton } from "@/components/feedback/route-skeletons";

export default function Loading() {
  return <ListPageSkeleton label="Loading supporting documents" columns={6} withAction={false} />
}
