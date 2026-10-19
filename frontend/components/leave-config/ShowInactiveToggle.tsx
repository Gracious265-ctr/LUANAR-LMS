"use client";

import { useRouter } from "next/navigation";

import { Checkbox } from "@/components/ui/checkbox";

/**
 * "Show inactive" — spec 3.2's one filter.
 *
 * It is a navigation, not local state: the server component decides what the
 * list contains, so flipping the box pushes the query param the page already
 * reads. That keeps a shared link to "everything, retired included" working
 * and keeps the list server-rendered.
 */
export function ShowInactiveToggle({ checked }: { checked: boolean }) {
  const router = useRouter();

  return (
    <div className="flex justify-end">
      <label
        htmlFor="show-inactive"
        className="inline-flex cursor-pointer items-center gap-2 text-sm text-text-secondary"
      >
        <Checkbox
          id="show-inactive"
          checked={checked}
          onCheckedChange={(next) =>
            router.push(
              next === true ? "/leave-config?include_inactive=true" : "/leave-config"
            )
          }
        />
        Show inactive
      </label>
    </div>
  );
}
