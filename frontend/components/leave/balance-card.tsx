"use client";

import { Wallet } from "lucide-react";
import { Card } from "@/components/ui/card";

interface BalanceCardProps {
  availableBalance: string | null;
  balanceAfter: string | null;
  financialYear: string | null;
}

/**
 * Shows the approved-deduction balance for annual-deducting leave types only.
 * The parent renders this card when the validation result exposes a balance.
 */
export function BalanceCard({
  availableBalance,
  balanceAfter,
  financialYear,
}: BalanceCardProps) {
  return (
    <Card>
      <div className="flex items-center gap-2 text-text-secondary mb-4">
        <Wallet className="h-4 w-4" />
        <h3 className="text-base font-semibold text-text-primary">
          Annual Leave Balance
        </h3>
        {financialYear && (
          <span className="ml-auto text-xs text-text-muted">
            {financialYear}
          </span>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-xs text-text-muted mb-1">Available balance</dt>
          <dd className="text-2xl font-semibold tracking-tight text-text-primary">
            {availableBalance ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted mb-1">Balance if approved</dt>
          <dd className="text-2xl font-semibold tracking-tight text-brand-secondary">
            {balanceAfter ?? "—"}
          </dd>
        </div>
      </dl>
      <p className="text-xs text-text-muted mt-4">
        Nothing is deducted until your application is finally approved.
      </p>
    </Card>
  );
}