import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinancialYearCarryOverButton } from "@/components/hr/financial-year-carry-over-button";
import { FinancialYearsSection } from "@/components/hr/FinancialYearsSection";
import { Toaster } from "@/components/ui/toast";
import type { CarryOverResult, FinancialYear } from "@/lib/financial-years";
import { runCarryOver } from "@/lib/financial-years-client";

const refresh = vi.fn();
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, push, replace, back: vi.fn() }),
  usePathname: () => "/dashboard/hr-admin/calendar",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/financial-years-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/financial-years-client")>();
  return { ...actual, runCarryOver: vi.fn() };
});

const mockedRun = vi.mocked(runCarryOver);

const active: FinancialYear = {
  id: 1,
  start_date: "2025-07-01",
  end_date: "2026-06-30",
  is_active: true,
};

const closing: FinancialYear = {
  id: 2,
  start_date: "2026-07-01",
  end_date: "2027-06-30",
  is_active: false,
};

const upcoming: FinancialYear = {
  id: 3,
  start_date: "2027-07-01",
  end_date: "2028-06-30",
  is_active: false,
};

function result(overrides: Partial<CarryOverResult> = {}): CarryOverResult {
  return {
    from_financial_year: "2025-26",
    to_financial_year: "2026-27",
    dry_run: false,
    employees: [{ employee_id: 7, days: "4", created: true }],
    total_days: "4",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FinancialYearCarryOverButton", () => {
  it("runs the rollover and reports what was carried", async () => {
    mockedRun.mockResolvedValue(result());
    render(
      <>
        <FinancialYearCarryOverButton year={active} />
        <Toaster />
      </>
    );

    fireEvent.click(screen.getByRole("button", { name: /Carry over/ }));

    await waitFor(() => expect(mockedRun).toHaveBeenCalledWith(1));
    expect(
      await screen.findByText(/Carried 4 days into 2026-27 for 1 employee/)
    ).toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
  });

  it("does not claim a fresh grant when nothing new was written", async () => {
    mockedRun.mockResolvedValue(
      result({ employees: [{ employee_id: 7, days: "4", created: false }] })
    );
    render(
      <>
        <FinancialYearCarryOverButton year={active} />
        <Toaster />
      </>
    );

    fireEvent.click(screen.getByRole("button", { name: /Carry over/ }));

    expect(
      await screen.findByText(/was already applied/)
    ).toBeInTheDocument();
  });

  it("says when there was nothing to carry", async () => {
    mockedRun.mockResolvedValue(result({ employees: [], total_days: "0" }));
    render(
      <>
        <FinancialYearCarryOverButton year={active} />
        <Toaster />
      </>
    );

    fireEvent.click(screen.getByRole("button", { name: /Carry over/ }));

    expect(
      await screen.findByText(/Nothing to carry from 2025-26/)
    ).toBeInTheDocument();
  });

  it("surfaces a backend error", async () => {
    mockedRun.mockRejectedValue(new Error("No financial year is configured."));
    render(
      <>
        <FinancialYearCarryOverButton year={active} />
        <Toaster />
      </>
    );

    fireEvent.click(screen.getByRole("button", { name: /Carry over/ }));

    expect(
      await screen.findByText("No financial year is configured.")
    ).toBeInTheDocument();
  });
});

describe("FinancialYearsSection carry-over eligibility", () => {
  it("offers carry-over on each year that has begun and has a successor", () => {
    // Active (2025-26 → 2026-27) and closing (2026-27 → 2027-28) both qualify.
    render(<FinancialYearsSection years={[active, closing, upcoming]} />);

    expect(
      screen.getAllByRole("button", { name: /Carry over/ })
    ).toHaveLength(2);
  });

  it("hides carry-over on an upcoming year", () => {
    // The upcoming period starts after today, so it has no rejections to audit.
    render(<FinancialYearsSection years={[upcoming]} />);

    expect(
      screen.queryByRole("button", { name: /Carry over/ })
    ).not.toBeInTheDocument();
  });

  it("hides carry-over when no following year is configured", () => {
    render(<FinancialYearsSection years={[active]} />);

    expect(
      screen.queryByRole("button", { name: /Carry over/ })
    ).not.toBeInTheDocument();
  });
});
