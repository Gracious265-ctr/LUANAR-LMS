import { UserCheck } from "lucide-react";

import { CoverRequestSection } from "@/components/approvals/CoverRequestSection";
import { DelegationTable } from "@/components/hr/delegation-table";
import type { DelegateCandidate, Delegation } from "@/lib/delegations";
import { Card } from "@/components/ui/card";

export const COVER_BASE_HREF = "/approvals/cover";

/**
 * An approver's own cover view.
 *
 * Rendered both as the "Cover" tab of /approvals and as the
 * dedicated /approvals/cover route the sidebar links to, so the two entry points
 * share one implementation. Data arrives as props because both callers are
 * server components; the list endpoint scopes a non-HR caller to the delegations
 * they are a party to, so this shows both the cover the approver handed over and
 * the cover they are receiving.
 */
export function CoverPanel({
  delegations,
  candidates,
  error,
}: {
  delegations: Delegation[] | null;
  candidates: DelegateCandidate[];
  error?: string;
}) {
  return (
    <div className="space-y-6">
      <Card>
        <CoverRequestSection candidates={candidates} />
      </Card>

      <Card>
        <div className="mb-4 flex items-center gap-2">
          <UserCheck className="h-5 w-5 text-text-secondary" />
          <h3 className="text-lg font-semibold text-text-primary">
            Your delegations
          </h3>
        </div>
        {error || !delegations ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {error || "Unable to load your delegations. Please try again."}
          </div>
        ) : (
          <DelegationTable
            delegations={delegations}
            baseHref={COVER_BASE_HREF}
            emptyHint="You have no delegation requests. Use the form above when you need someone to approve while you are away."
          />
        )}
      </Card>
    </div>
  );
}
