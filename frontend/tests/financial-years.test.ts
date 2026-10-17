import { describe, expect, it } from "vitest";

import type { FinancialYear } from "@/lib/financial-years";
import { financialYearStatus } from "@/lib/financial-years";

const active: FinancialYear = {
  id: 1,
  start_date: "2025-07-01",
  end_date: "2026-06-30",
  is_active: true,
};

const upcoming: FinancialYear = {
  id: 2,
  start_date: "2027-07-01",
  end_date: "2028-06-30",
  is_active: false,
};

const past: FinancialYear = {
  id: 3,
  start_date: "2023-07-01",
  end_date: "2024-06-30",
  is_active: false,
};

describe("financialYearStatus", () => {
  it("returns active for the flagged financial year", () => {
    expect(financialYearStatus(active, "2026-09-17")).toBe("active");
  });

  it("returns upcoming for a future-dated inactive year", () => {
    expect(financialYearStatus(upcoming, "2026-09-17")).toBe("upcoming");
  });

  it("returns past for an ended, non-active year", () => {
    expect(financialYearStatus(past, "2026-09-17")).toBe("past");
  });
});