/**
 * Render a financial-year label ("2026-27") as "FY 2026-27".
 */
export function formatFinancialYear(
  value: string | null | undefined
): string {
  if (!value) return "";
  return `FY ${value}`;
}

/**
 * "Starts in N days" label for the approver list. The leave-started flag comes
 * from the server; the date is used only for display when it has not started.
 * Returns a label plus a variant for colouring (soon / started / plain).
 */
export function startsInLabel(
  startDate: string | null,
  leaveStarted: boolean
): { label: string; variant: "soon" | "started" | "plain" } {
  if (leaveStarted) return { label: "Started", variant: "started" };
  if (!startDate) return { label: "—", variant: "plain" };

  const [year, month, day] = startDate.split("-").map(Number);
  if (!year || !month || !day) return { label: "—", variant: "plain" };

  const today = new Date();
  const start = Date.UTC(year, month - 1, day);
  const now = Date.UTC(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  );
  const days = Math.round((start - now) / 86_400_000);

  if (days < 0) return { label: "Started", variant: "started" };
  if (days === 0) return { label: "Starts today", variant: "soon" };
  if (days <= 3) {
    return {
      label: `Starts in ${days} ${days === 1 ? "day" : "days"}`,
      variant: "soon",
    };
  }
  return { label: `Starts in ${days} days`, variant: "plain" };
}