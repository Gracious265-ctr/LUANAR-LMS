import { BalanceRing } from "@/components/ui/BalanceRing";
import type { LeaveBalance } from "@/lib/leave-dashboard";

/**
 * Read-only balance display — one ring per entitlement the employee holds.
 * The dashboard summary already caps this at four rings server-side, so this
 * is a straight map with no overflow handling.
 */
export function BalanceSection({ balances }: { balances: LeaveBalance[] }) {
  return (
    <section aria-labelledby="balance-heading">
      <h2
        id="balance-heading"
        className="mb-3 text-lg font-semibold text-text-primary"
      >
        Your Balance
      </h2>
      {balances.length === 0 ? (
        <p className="text-sm text-text-muted">
          No leave balances are available for the current year yet.
        </p>
      ) : (
        <div className="flex flex-wrap gap-6">
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
    </section>
  );
}
