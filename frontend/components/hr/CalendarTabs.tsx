"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import type {
  CalendarEvent,
  FinancialYear,
  Holiday,
  WorkingDayPattern,
} from "@/lib/financial-years";
import { FinancialYearsSection } from "@/components/hr/FinancialYearsSection";
import { HolidaysSection } from "@/components/hr/HolidaysSection";
import { EventsSection } from "@/components/hr/EventsSection";
import { WorkingDaysSection } from "@/components/hr/WorkingDaysSection";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type CalendarTab = "financial-years" | "holidays" | "working-days";

const TABS: { value: CalendarTab; label: string }[] = [
  { value: "financial-years", label: "Financial Years" },
  { value: "holidays", label: "Holidays & Events" },
  { value: "working-days", label: "Working Days" },
];

/**
 * The Calendar app's tabbed landing page (§3.3).
 *
 * One page, three tabs, rather than a sidebar item per concept — the same
 * "don't proliferate nav items" discipline the Leave Plans page follows. The
 * month grid is a slot so the server page can resolve holidays for the shown
 * month and hand the client component finished data.
 */
export function CalendarTabs({
  initialTab,
  grid,
  financialYears,
  holidays,
  holidayYearFilter,
  holidayFilter,
  events,
  workingDays,
}: {
  initialTab: CalendarTab;
  /** The month grid, resolved server-side for the shown month. */
  grid?: ReactNode;
  financialYears: FinancialYear[];
  holidays: Holiday[];
  holidayYearFilter: string;
  /** The server page's `?year` GET form, rendered inside the holidays tab. */
  holidayFilter?: ReactNode;
  events: CalendarEvent[];
  workingDays: WorkingDayPattern;
}) {
  const [view, setView] = useState<CalendarTab>(initialTab);

  return (
    <Tabs
      value={view}
      className="contents"
      onValueChange={(next) => setView(next as CalendarTab)}
    >
      <TabsList variant="segmented" aria-label="Calendar">
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} variant="segmented" value={tab.value}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {view === "financial-years" ? (
        <FinancialYearsSection years={financialYears} />
      ) : view === "holidays" ? (
        <div className="space-y-6">
          {grid}
          <HolidaysSection
            holidays={holidays}
            financialYears={financialYears}
            yearFilter={holidayYearFilter}
            filter={holidayFilter}
          />
          <EventsSection events={events} />
        </div>
      ) : (
        <WorkingDaysSection pattern={workingDays} />
      )}
    </Tabs>
  );
}
