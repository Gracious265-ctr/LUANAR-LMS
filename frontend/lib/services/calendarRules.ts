export async function previewWorkingDays(
  startDate: string,
  endDate: string
): Promise<{ days: number }> {
  const res = await fetch("/api/leave/preview-days/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  });
  if (!res.ok) throw new Error("Failed to calculate working days");
  return res.json();
}
