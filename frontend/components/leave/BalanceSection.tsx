import { BalanceRing } from "@/components/ui/BalanceRing";
import { Card } from "@/components/ui/card";
import type { LeaveBalance } from "@/lib/leave-dashboard";

/**
 * Read-only balance display — one ring per entitlement the employee holds,
 * presented as a card so the answer to "how much leave have I left" reads as a
 * panel beside the lists rather than as loose figures in the rail.
 *
 * The dashboard summary already caps this at four rings server-side, so this is
 * a straight map with no overflow handling.
 */
export function BalanceSection({ balances }: { balances: LeaveBalance[] }) {
  return (
    <section aria-labelledby="balance-heading">
      <Card>
        <h2
          id="balance-heading"
          className="text-lg font-semibold text-text-primary"
        >
          Your Balance
        </h2>
        {balances.length === 0 ? (
          <div className="mt-4">
            <p className="text-sm text-text-secondary">
              No leave balances are available for the current year yet.
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Contact HR if you expect balances to appear.
            </p>
          </div>
        ) : (
          <div className="mt-5 flex flex-wrap gap-6">
            {balances.map((balance) => (
              <BalanceRing
                key={balance.leave_type}
                label={balance.leave_type}
                used={balance.used}
                total={balance.total}
              />
            ))}
          </div>
        )}
      </Card>
    </section>
  );
}
