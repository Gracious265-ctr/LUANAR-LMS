import Link from "next/link";
import { Compass } from "lucide-react";

import { EmptyPanel } from "@/components/ui/states";
import { buttonVariants } from "@/components/ui/button";

/**
 * Renders inside the root layout, so it has no dashboard shell and needs to
 * centre itself.
 */
export default function NotFound() {
  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <EmptyPanel
        className="max-w-md"
        icon={<Compass className="size-8" aria-hidden="true" />}
        title="We could not find that page"
        description="The link may be out of date, or the record may have been removed."
        action={
          <Link
            href="/dashboard"
            className={buttonVariants({ variant: "primary", size: "lg" })}
          >
            Back to dashboard
          </Link>
        }
      />
    </main>
  );
}
