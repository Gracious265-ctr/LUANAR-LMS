"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { runCarryOver } from "@/lib/financial-years-client";
import type { FinancialYear } from "@/lib/financial-years";

/**
 * Run the rejected-leave rollover for one financial year.
 *
 * Writes each employee's eligible carry-over into the *following* year. The
 * backend decides the amount and is idempotent, so a second click grants
 * nothing extra — the confirm wording and the "already carried" result both
 * reflect that rather than pretending each click is a fresh grant.
 *
 * Only rendered for a year that is not still upcoming: a future period has no
 * rejections to audit yet.
 */
export function FinancialYearCarryOverButton({
  year,
  className,
}: {
  year: FinancialYear;
  className?: string;
}) {
  const router = useRouter();
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);

  const handleRun = async () => {
    setBusy(true);
    try {
      const result = await runCarryOver(year.id);
      const count = result.employees.length;
      if (count === 0) {
        showToast(
          `Nothing to carry from ${result.from_financial_year}.`,
          "info"
        );
      } else {
        const created = result.employees.filter((row) => row.created).length;
        showToast(
          created === 0
            ? `Carry-over for ${result.from_financial_year} was already applied.`
            : `Carried ${result.total_days} days into ${result.to_financial_year} for ${count} employee${count === 1 ? "" : "s"}.`,
          "success"
        );
      }
      router.refresh();
    } catch (err) {
      showToast(
        err instanceof Error
          ? err.message
          : "Could not run the carry-over. Please try again.",
        "error"
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={handleRun}
      disabled={busy}
      className={className}
      title={`Carry rejected leave from ${year.start_date} into the next year`}
    >
      <CalendarClock className="h-4 w-4" />
      {busy ? "Carrying…" : "Carry over"}
    </Button>
  );
}
