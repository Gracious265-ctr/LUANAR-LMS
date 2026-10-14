import { describe, expect, it } from "vitest";

import {
  formatDateRange,
  formatDisplayDate,
  fromIsoDate,
  isDateOutsideBounds,
  toIsoDate,
} from "@/lib/date";

describe("toIsoDate", () => {
  it("formats a Date as yyyy-MM-dd", () => {
    expect(toIsoDate(new Date(2026, 9, 5))).toBe("2026-10-05");
  });
});

describe("fromIsoDate", () => {
  it("parses an ISO date to local midnight", () => {
    const parsed = fromIsoDate("2026-10-05");

    expect(parsed).toBeInstanceOf(Date);
    expect(parsed?.getFullYear()).toBe(2026);
    expect(parsed?.getMonth()).toBe(9);
    expect(parsed?.getDate()).toBe(5);
    expect(parsed?.getHours()).toBe(0);
  });

  it("returns undefined for empty or invalid input", () => {
    expect(fromIsoDate("")).toBeUndefined();
    expect(fromIsoDate(undefined)).toBeUndefined();
    expect(fromIsoDate(null)).toBeUndefined();
    expect(fromIsoDate("not-a-date")).toBeUndefined();
  });
});

describe("formatDisplayDate", () => {
  it("formats an ISO date for humans", () => {
    expect(formatDisplayDate("2026-10-05")).toBe("05 Oct 2026");
  });

  it("returns an empty string when there is no date", () => {
    expect(formatDisplayDate("")).toBe("");
  });
});

describe("formatDateRange", () => {
  it("joins both ends of a complete range", () => {
    expect(formatDateRange("2026-10-05", "2026-10-09")).toBe(
      "05 Oct 2026 – 09 Oct 2026"
    );
  });

  it("marks an open-ended range", () => {
    expect(formatDateRange("2026-10-05", "")).toBe("05 Oct 2026 – …");
  });

  it("returns an empty string when nothing is selected", () => {
    expect(formatDateRange("", "")).toBe("");
  });
});

describe("isDateOutsideBounds", () => {
  const day = new Date(2026, 9, 5);

  it("treats both bounds as inclusive", () => {
    expect(isDateOutsideBounds(day, "2026-10-05", "2026-10-05")).toBe(false);
  });

  it("rejects days before min and after max", () => {
    expect(isDateOutsideBounds(day, "2026-10-06")).toBe(true);
    expect(isDateOutsideBounds(day, undefined, "2026-10-04")).toBe(true);
  });

  it("allows everything when no bounds are given", () => {
    expect(isDateOutsideBounds(day)).toBe(false);
  });
});
