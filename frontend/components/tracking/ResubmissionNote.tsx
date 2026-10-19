import { RefreshCw } from "lucide-react";

import { formatDateTime } from "@/lib/tracking/format";
import type { ResubmissionInfo } from "@/lib/tracking/types";

/**
 * Shown when ``resubmission.count > 0``. The reference number never changes on
 * resubmission (shown in the header).
 */
export function ResubmissionNote({
  resubmission,
}: {
  resubmission: ResubmissionInfo;
}) {
  if (resubmission.count <= 0) return null;

  return (
    <section
      aria-label="Resubmission"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <div className="flex items-center gap-2">
        <RefreshCw className="h-5 w-5 text-text-secondary" aria-hidden="true" />
        <h2 className="text-base font-semibold text-text-primary">
          Resubmission
        </h2>
      </div>
      <p className="mt-2 text-sm text-text-secondary">
        Resubmitted {resubmission.count}{" "}
        {resubmission.count === 1 ? "time" : "times"} · last on{" "}
        {resubmission.last_resubmitted_at && (
          <time dateTime={resubmission.last_resubmitted_at}>
            {formatDateTime(resubmission.last_resubmitted_at)}
          </time>
        )}
      </p>
    </section>
  );
}