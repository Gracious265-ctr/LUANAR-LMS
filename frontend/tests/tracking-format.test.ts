import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime } from "@/lib/tracking/format";

describe("formatDateTime", () => {
  it("converts a UTC instant to Africa/Blantyre (UTC+2)", () => {
    expect(formatDateTime("2026-10-14T07:15:03Z")).toBe("14 Oct 2026, 09:15");
  });

  it("handles nullish and empty values", () => {
    expect(formatDateTime(null)).toBe("");
    expect(formatDateTime(undefined)).toBe("");
    expect(formatDateTime("")).toBe("");
  });
});

describe("formatDate", () => {
  it("formats calendar dates without any time-zone shift", () => {
    expect(formatDate("2026-11-02")).toBe("2 Nov 2026");
    expect(formatDate("2026-12-18")).toBe("18 Dec 2026");
  });

  it("handles nullish and malformed values", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
    expect(formatDate("not-a-date")).toBe("");
  });
});