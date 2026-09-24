// @vitest-environment node
import { describe, expect, it } from "vitest";

import { formatIsoDate } from "@/lib/leave-overview";

describe("formatIsoDate", () => {
  it("formats YYYY-MM-DD as a readable date", () => {
    expect(formatIsoDate("2022-03-15")).toBe("15 Mar 2022");
    expect(formatIsoDate("2026-01-01")).toBe("01 Jan 2026");
    expect(formatIsoDate("2027-12-31")).toBe("31 Dec 2027");
  });

  it("returns the input unchanged when it is not a date", () => {
    expect(formatIsoDate("not-a-date")).toBe("not-a-date");
    expect(formatIsoDate("2026-13-15")).toBe("2026-13-15");
  });
});