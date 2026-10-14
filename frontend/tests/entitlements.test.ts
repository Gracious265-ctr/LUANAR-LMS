// @vitest-environment node
import { describe, expect, it } from "vitest";

import { Entitlement } from "@/lib/entitlements";
import {
  expandGradeRange,
  gradeOptionsFromEntitlements,
} from "@/lib/entitlements";
import { isAnnualLeaveType } from "@/lib/leave-rules";
import { currentDateIso } from "@/lib/utils";

describe("isAnnualLeaveType", () => {
  it("recognises either code the annual type is provisioned under", () => {
    expect(isAnnualLeaveType({ code: "annual" })).toBe(true);
    expect(isAnnualLeaveType({ code: "annual-leave" })).toBe(true);
    expect(isAnnualLeaveType({ code: "Annual-Leave" })).toBe(true);
  });

  it("does not claim any other leave type", () => {
    expect(isAnnualLeaveType({ code: "maternity" })).toBe(false);
    expect(isAnnualLeaveType({ code: "study" })).toBe(false);
    expect(isAnnualLeaveType({ code: "anniversary" })).toBe(false);
    expect(isAnnualLeaveType(null)).toBe(false);
    expect(isAnnualLeaveType(undefined)).toBe(false);
  });
});

describe("currentDateIso", () => {
  it("formats the date in the app time zone, not UTC", () => {
    expect(currentDateIso(new Date("2026-09-16T23:30:00Z"))).toBe("2026-09-17");
    expect(currentDateIso(new Date("2026-09-17T00:30:00Z"))).toBe("2026-09-17");
  });
});

describe("expandGradeRange", () => {
  it("expands single-character letter ranges inclusive", () => {
    expect(expandGradeRange("A", "C")).toEqual(["A", "B", "C"]);
    expect(expandGradeRange("H", "U")).toHaveLength(14);
  });

  it("falls back to endpoints for non-letter or reversed ranges", () => {
    expect(expandGradeRange("P1", "P3")).toEqual(["P1", "P3"]);
    expect(expandGradeRange("C", "A")).toEqual(["C", "A"]);
  });
});

describe("gradeOptionsFromEntitlements", () => {
  const entitlements: Entitlement[] = [
    {
      id: 1,
      grade_start: "D",
      grade_end: "G",
      days: 24,
      effective_from: "2025-01-01",
      leave_type: null,
    },
    {
      id: 2,
      grade_start: "A",
      grade_end: "C",
      days: 21,
      effective_from: "2025-01-01",
      leave_type: null,
    },
    {
      id: 3,
      grade_start: "H",
      grade_end: "U",
      days: 30,
      effective_from: "2030-01-01",
      leave_type: null,
    },
  ];

  it("returns sorted unique grades from currently effective ranges only", () => {
    expect(gradeOptionsFromEntitlements(entitlements, "2026-09-17")).toEqual([
      "A",
      "B",
      "C",
      "D",
      "E",
      "F",
      "G",
    ]);
  });

  it("includes future ranges once they become effective", () => {
    expect(gradeOptionsFromEntitlements(entitlements, "2030-01-01")[0]).toBe(
      "A"
    );
  });
});