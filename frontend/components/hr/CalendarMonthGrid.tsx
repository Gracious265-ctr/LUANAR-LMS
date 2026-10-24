import type {
  CalendarEvent,
  ResolvedHoliday,
  WorkingDayPattern,
} from "@/lib/financial-years";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const HEADER_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const JS_DAY_TO_WEEKDAY = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
] as const;

function iso(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/**
 * A plain month grid for the Calendar app (§3.2, §4: no calendar library).
 *
 * Its whole job is the visual distinction the spec makes mandatory: this app's
 * entries render as **solid filled day cells**, which is deliberately unlike
 * the Team Plans calendar's dashed/outlined bars. Non-working days are shaded
 * from the working-day pattern, holidays carry the brand fill, and events carry
 * a secondary fill so the two entry kinds stay tellable apart at a glance.
 */
export function CalendarMonthGrid({
  year,
  month,
  holidays,
  events,
  workingDays,
}: {
  year: number;
  /** 1–12. */
  month: number;
  /** Occurrences resolved for this month, with `observed_shift` applied. */
  holidays: ResolvedHoliday[];
  /** Events overlapping this month. */
  events: CalendarEvent[];
  workingDays: WorkingDayPattern;
}) {
  const firstOfMonth = new Date(Date.UTC(year, month - 1, 1));
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const leadingBlanks = (firstOfMonth.getUTCDay() + 6) % 7;
  const totalCells = Math.ceil((leadingBlanks + daysInMonth) / 7) * 7;

  const holidayByDate = new Map<string, string>();
  for (const holiday of holidays) {
    holidayByDate.set(holiday.date, holiday.name);
  }

  const monthStart = iso(year, month, 1);
  const monthEnd = iso(year, month, daysInMonth);
  const eventsByDate = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    // Skip events that do not overlap the shown month at all; without this the
    // day-of-month slices below would clip a far-away event onto this month.
    if (event.end_date < monthStart || event.start_date > monthEnd) continue;
    const spanStart = event.start_date < monthStart
      ? 1
      : Number(event.start_date.slice(8, 10));
    const spanEnd = event.end_date > monthEnd
      ? daysInMonth
      : Number(event.end_date.slice(8, 10));
    for (let day = spanStart; day <= spanEnd; day += 1) {
      const key = iso(year, month, day);
      const list = eventsByDate.get(key) ?? [];
      list.push(event);
      eventsByDate.set(key, list);
    }
  }

  return (
    <div className="rounded-lg border border-border-default p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          {MONTH_NAMES[month - 1]} {year}
        </h3>
        <span className="text-xs text-text-muted">
          Solid cells — this institution&apos;s calendar
        </span>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-text-muted">
        {HEADER_DAYS.map((day) => (
          <div key={day} className="py-1">
            {day}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: totalCells }).map((_, index) => {
          const dayNumber = index - leadingBlanks + 1;
          if (dayNumber < 1 || dayNumber > daysInMonth) {
            return <div key={index} className="min-h-16 rounded-md" />;
          }
          const key = iso(year, month, dayNumber);
          const weekday = JS_DAY_TO_WEEKDAY[
            new Date(Date.UTC(year, month - 1, dayNumber)).getUTCDay()
          ];
          const isWorking = workingDays[weekday];
          const holidayName = holidayByDate.get(key);
          const dayEvents = eventsByDate.get(key) ?? [];

          return (
            <div
              key={index}
              className={[
                "min-h-16 rounded-md border p-1 text-left",
                isWorking
                  ? "border-border-default"
                  : "border-transparent bg-surface-muted",
              ].join(" ")}
            >
              <div
                className={[
                  "inline-flex h-5 w-5 items-center justify-center rounded text-[11px] font-semibold",
                  holidayName
                    ? "bg-brand-primary text-white"
                    : isWorking
                      ? "text-text-primary"
                      : "text-text-muted",
                ].join(" ")}
              >
                {dayNumber}
              </div>
              {holidayName && (
                <p className="mt-1 line-clamp-2 text-[11px] font-medium text-brand-primary">
                  {holidayName}
                </p>
              )}
              {dayEvents.map((event) => (
                <p
                  key={event.id}
                  className="mt-1 line-clamp-2 rounded bg-brand-secondary-subtle px-1 text-[11px] text-brand-secondary"
                >
                  {event.title}
                </p>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
