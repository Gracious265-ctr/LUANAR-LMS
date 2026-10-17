import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  usePathname: () => "/dashboard/plans",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/hooks/usePlans", () => ({ usePlans: vi.fn() }));
vi.mock("@/lib/plans/service", () => ({
  applyPlan: vi.fn(),
  cancelPlan: vi.fn(),
}));

import { MyPlans } from "@/components/plans/MyPlans";
import { usePlans } from "@/lib/hooks/usePlans";
import { applyPlan, cancelPlan } from "@/lib/plans/service";
import { makePlan } from "@/lib/plans/__fixtures__";
import type { LeavePlan } from "@/lib/plans/types";

function mockPlans(
  plans: LeavePlan[] | null,
  over: Record<string, unknown> = {}
) {
  vi.mocked(usePlans).mockReturnValue({
    data: plans,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    ...over,
  } as ReturnType<typeof usePlans>);
}

beforeEach(() => {
  vi.mocked(usePlans).mockReset();
  vi.mocked(applyPlan).mockReset();
  vi.mocked(cancelPlan).mockReset();
  push.mockReset();
});

describe("MyPlans", () => {
  it("splits live plans from history", () => {
    mockPlans([
      makePlan({ id: "live", status: "upcoming" }),
      makePlan({ id: "done", status: "converted", converted_application: "draft-1" }),
    ]);

    render(<MyPlans />);

    expect(screen.getByRole("heading", { name: "Planned leave" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Earlier plans" })).toBeInTheDocument();
  });

  it("shows the empty state when there are no plans", () => {
    mockPlans([]);
    render(<MyPlans />);
    expect(screen.getByText(/no leave plans yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create a plan/i })).toBeInTheDocument();
  });

  it("shows an error state when loading failed", () => {
    mockPlans(null, { error: "boom" });
    render(<MyPlans />);
    expect(screen.getByText(/couldn't load your plans/i)).toBeInTheDocument();
  });
});

describe("PlanCard actions", () => {
  it("Apply Now converts the plan and opens the draft editor", async () => {
    vi.mocked(applyPlan).mockResolvedValue({ application_id: "draft-42" });
    mockPlans([makePlan({ id: "plan-9", status: "notified" })]);

    render(<MyPlans />);
    fireEvent.click(screen.getByRole("button", { name: /apply now/i }));

    await waitFor(() => expect(applyPlan).toHaveBeenCalledWith("plan-9"));
    expect(push).toHaveBeenCalledWith("/dashboard/leave/drafts?edit=draft-42");
  });

  it("surfaces an apply failure instead of navigating", async () => {
    vi.mocked(applyPlan).mockRejectedValue(new Error("This plan has already been applied."));
    mockPlans([makePlan({ id: "plan-9", status: "notified" })]);

    render(<MyPlans />);
    fireEvent.click(screen.getByRole("button", { name: /apply now/i }));

    expect(
      await screen.findByText("This plan has already been applied.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("cancels a plan after confirmation and refreshes", async () => {
    const refetch = vi.fn();
    vi.mocked(cancelPlan).mockResolvedValue(undefined);
    mockPlans([makePlan({ id: "plan-9", status: "upcoming" })], { refetch });

    render(<MyPlans />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel plan" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    await waitFor(() => expect(cancelPlan).toHaveBeenCalledWith("plan-9"));
    expect(refetch).toHaveBeenCalled();
  });

  it("links a missed plan to re-plan with the same leave type", () => {
    mockPlans([makePlan({ id: "plan-9", status: "missed", leave_type_id: 7 })]);

    render(<MyPlans />);
    const link = screen.getByRole("button", { name: /plan a new one/i });
    fireEvent.click(link);

    expect(push).toHaveBeenCalledWith("/dashboard/plans/new?leaveType=7");
  });

  it("does not offer Apply Now for a finished plan", () => {
    mockPlans([makePlan({ status: "cancelled" })]);
    render(<MyPlans />);
    expect(screen.queryByRole("button", { name: /apply now/i })).not.toBeInTheDocument();
  });
});
