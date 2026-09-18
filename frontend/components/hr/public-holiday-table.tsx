import Link from "next/link";

import type { PublicHoliday } from "@/lib/financial-years";

export function PublicHolidayTable({
  holidays,
}: {
  holidays: PublicHoliday[];
}) {
  if (holidays.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No public holidays
        </p>
        <p className="mt-1 text-sm">
          Add the dates that should not count as working leave days.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Name</th>
            <th className="py-3 pr-4">Date</th>
          </tr>
        </thead>
        <tbody>
          {holidays.map((holiday) => (
            <tr
              key={holiday.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/calendar/holidays/${holiday.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {holiday.name}
                </Link>
              </td>
              <td className="py-3 pr-4 text-text-secondary">{holiday.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}