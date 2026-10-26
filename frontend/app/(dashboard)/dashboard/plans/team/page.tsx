"use client";

import { CalendarRange } from "lucide-react";

import { TeamPlansCalendar } from "@/components/plans/TeamPlansCalendar";

/** Team Plans — the scope-aware team calendar (spec 3.6). */
export default function TeamPlansPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
          Team Plans
        </h1>
        <p className="flex items-center gap-1.5 text-text-muted">
          <CalendarRange className="h-4 w-4" aria-hidden="true" />
          Planned leave across your team.
        </p>
      </div>

      <TeamPlansCalendar />
    </div>
  );
}
