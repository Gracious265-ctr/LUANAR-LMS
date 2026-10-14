import { describe, expect, it } from "vitest";

import {
  countOnDay,
  detectConflicts,
  eachDay,
  firstConflict,
} from "@/lib/calendar/conflicts";
import type { CalendarEntry } from "@/lib/calendar/types";

function entry(
  id: string,
  employeeId: number,
  start: string,
  end: string
): CalendarEntry {
  return {
    id,
    employee: { id: employeeId, name: `Person ${employeeId}` },
    start_date: start,
    end_date: end,
    leave_type: { id: 1, code: "ANNUAL", name: "Annual Leave" },
    status: "approved",
  };
}

const ENTRIES = [
  entry("a", 1, "2026-10-05", "2026-10-07"),
  entry("b", 2, "2026-10-06", "2026-10-08"),
  entry("c", 3, "2026-10-06", "2026-10-06"),
];

describe("eachDay", () => {
  it("walks every date inclusive", () => {
    expect(eachDay("2026-10-05", "2026-10-08")).toEqual([
      "2026-10-05",
      "2026-10-06",
      "2026-10-07",
      "2026-10-08",
    ]);
  });

  it("returns nothing for a reversed or empty range", () => {
    expect(eachDay("2026-10-08", "2026-10-05")).toEqual([]);
    expect(eachDay("", "")).toEqual([]);
  });
});

describe("countOnDay", () => {
  it("counts entries covering the day", () => {
    expect(countOnDay(ENTRIES, "2026-10-06")).toBe(3);
    expect(countOnDay(ENTRIES, "2026-10-07")).toBe(2);
    expect(countOnDay(ENTRIES, "2026-10-09")).toBe(0);
  });
});

describe("detectConflicts", () => {
  it("flags only days over the threshold, as a run", () => {
    expect(detectConflicts(ENTRIES, 2)).toEqual([
      { start: "2026-10-06", end: "2026-10-06", count: 3 },
    ]);
  });

  it("widens the run when the threshold is lower", () => {
    expect(detectConflicts(ENTRIES, 1)).toEqual([
      { start: "2026-10-06", end: "2026-10-07", count: 3 },
    ]);
  });

  it("reports the peak of a multi-day run", () => {
    const entries = [
      entry("a", 1, "2026-10-01", "2026-10-04"),
      entry("b", 2, "2026-10-01", "2026-10-04"),
      entry("c", 3, "2026-10-01", "2026-10-04"),
      entry("d", 4, "2026-10-02", "2026-10-02"),
    ];
    expect(detectConflicts(entries, 3)).toEqual([
      { start: "2026-10-02", end: "2026-10-02", count: 4 },
    ]);
  });

  it("honours a bound so days outside the drawn month are ignored", () => {
    // The conflict is on Oct 6; asking about November returns nothing.
    expect(
      detectConflicts(ENTRIES, 2, {
        start: "2026-11-01",
        end: "2026-11-30",
      })
    ).toEqual([]);
  });

  it("returns nothing for no entries", () => {
    expect(detectConflicts([], 2)).toEqual([]);
  });
});

describe("firstConflict", () => {
  it("returns the first over-cap day within the request window", () => {
    expect(
      firstConflict(ENTRIES, 2, "2026-10-05", "2026-10-07")
    ).toEqual({ day: "2026-10-06", count: 3 });
  });

  it("is null when the window stays within the cap", () => {
    expect(
      firstConflict(ENTRIES, 2, "2026-10-01", "2026-10-05")
    ).toBeNull();
  });
});
