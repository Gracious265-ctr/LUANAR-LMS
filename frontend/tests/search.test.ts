import { describe, expect, it } from "vitest";

import { matchesSearch } from "@/lib/search";

describe("matchesSearch", () => {
  it("matches everything when the query is empty or only whitespace", () => {
    expect(matchesSearch("", ["Annual Leave"])).toBe(true);
    expect(matchesSearch("   ", ["Annual Leave"])).toBe(true);
  });

  it("ignores case and matches any of the row's values", () => {
    expect(
      matchesSearch("ANNUAL", ["LV-2026-27-000001", "Annual Leave"])
    ).toBe(true);
    expect(matchesSearch("lv-2026", ["LV-2026-27-000001", "Annual Leave"])).toBe(
      true
    );
  });

  it("requires every token to appear somewhere in the row", () => {
    expect(matchesSearch("jane dean", ["Jane M. Dean", "jane@test.luanar"])).toBe(
      true
    );
    expect(matchesSearch("jane registrar", ["Jane M. Dean", "Lecturer"])).toBe(
      false
    );
  });

  it("treats missing values as empty rather than matching their text", () => {
    expect(matchesSearch("null", [null, undefined, "Annual Leave"])).toBe(false);
  });

  it("matches numbers, so a grade band or day count is searchable", () => {
    expect(matchesSearch("21", ["G", "H", 21])).toBe(true);
  });
});
