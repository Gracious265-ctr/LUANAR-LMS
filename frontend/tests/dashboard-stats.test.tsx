import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/(dashboard)/dashboard/page";
import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import type { LeaveSummary } from "@/lib/leave-summary";
import { getLeaveSummary } from "@/lib/leave-summary";

vi.mock("@/lib/auth", () => ({ getCurrentUser: vi.fn() }));
vi.mock("@/lib/approvals/capabilities", () => ({
  loadApprovalCapabilities: vi.fn(),
}));
vi.mock("@/lib/leave-summary", () => ({ getLeaveSummary: vi.fn() }));
// The page imports `redirect` statically; the setup file's mock predates it and
// only supplies the router hooks, so this file declares its own.
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));

const summary: LeaveSummary = {
  profile: null,
  entitlement: null,
  financial_year: null,
  available_balance: "24",
  carry_over_days: null,
  pending_applications: 3,
  upcoming_leave: { days: 5, applications: 1 },
};

/** The card whose `<span>` title matches, so assertions cannot cross wires. */
function card(title: string) {
  const heading = screen.getByText(title);
  const container = heading.parentElement?.parentElement;
  if (!container) {
    throw new Error(`no card found for "${title}"`);
  }
  return within(container);
}

/** The big number in one card — the only all-digits text it contains. */
function valueIn(title: string): string {
  return card(title).getByText(/^\d+$/).textContent ?? "";
}

describe("dashboard stat cards", () => {
  beforeEach(() => {
    vi.mocked(getCurrentUser).mockResolvedValue({
      id: 1,
      email: "employee@luanar",
      role: "employee",
      full_name: "Ken Employee",
    });
    vi.mocked(loadApprovalCapabilities).mockResolvedValue({
      is_approver: false,
      pending_count: 0,
    });
    vi.mocked(getLeaveSummary).mockResolvedValue(summary);
  });

  it("shows the employee's own pending and upcoming numbers", async () => {
    render(await DashboardPage());

    expect(valueIn("Pending Applications")).toBe("3");
    expect(valueIn("Upcoming Leave")).toBe("5");
  });

  it("keeps the applicant count separate from the approver count", async () => {
    // Two populations that are easy to cross-wire: what this person has sent,
    // and what they are being asked to decide.
    vi.mocked(loadApprovalCapabilities).mockResolvedValue({
      is_approver: true,
      pending_count: 7,
    });

    render(await DashboardPage());

    expect(valueIn("Pending Applications")).toBe("3");
    expect(valueIn("Awaiting My Approval")).toBe("7");
  });

  it("falls back to zero when the summary could not be loaded", async () => {
    vi.mocked(getLeaveSummary).mockResolvedValue(null);

    render(await DashboardPage());

    expect(valueIn("Pending Applications")).toBe("0");
    expect(valueIn("Upcoming Leave")).toBe("0");
    // The balance degrades on its own terms: a dash, not a zero.
    expect(card("Available Balance").getByText("—")).toBeDefined();
  });
});
