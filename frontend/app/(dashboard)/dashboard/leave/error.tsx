"use client";

import { RouteError } from "@/components/feedback/route-error";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return <RouteError error={error} retry={retry} title="Leave could not load" />;
}
