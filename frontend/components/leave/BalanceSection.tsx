import { BalanceRing } from "@/components/ui/BalanceRing";
import { Card } from "@/components/ui/card";
import type { LeaveBalance } from "@/lib/leave-dashboard";

/**
 * Read-only balance display — one ring per entitlement the employee holds,
 * presented as a card so the answer to "how much leave have I left" reads as a
 * panel beside the lists rather than as loose figures in the rail.
 *
 * The heading uses the stat cards' title style, and each ring sits beside its
 * label instead of above it, so the panel is the same height as the Pending
 * Applications and Upcoming Leave cards it shares a row with. `h-full` fills
 * that row — if the balance list makes this panel the tallest, the two stat
 * cards stretch to it — and the min-height holds the footprint when there is no
 * balance to draw.
 *
 * The dashboard summary already caps this at four rings server-side, so this is
 * a straight map with no overflow handling.
 */
export function BalanceSection({ balances }: { balances: LeaveBalance[] }) {
  return (
    <section aria-labelledby="balance-heading" className="h-full">
      <Card className="h-full min-h-[10.75rem]">
        <h2
          id="balance-heading"
          className="text-sm font-medium text-text-secondary"
        >
          Your Balance
        </h2>
        {balances.length === 0 ? (
          <div className="mt-3">
            <p className="text-sm text-text-secondary">
              No leave balances are available for the current year yet.
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Contact HR if you expect balances to appear.
            </p>
          </div>
        ) : (
          <ul className="mt-2 space-y-3">
            {balances.map((balance) => (
              <li key={balance.leave_type}>
                <BalanceRing
                  label={balance.leave_type}
                  used={balance.used}
                  total={balance.total}
                  size={80}
                />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}
