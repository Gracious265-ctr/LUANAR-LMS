import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  usePathname: () => "/dashboard/plans/plan-1",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/plans/service", () => ({ applyPlan: vi.fn() }));

import { PlanDetail } from "@/components/plans/PlanDetail";
import { applyPlan } from "@/lib/plans/service";
import { makePlan } from "@/lib/plans/__fixtures__";

beforeEach(() => {
  vi.mocked(applyPlan).mockReset();
  push.mockReset();
});

describe("PlanDetail", () => {
  it("shows the leave type, status and date range", () => {
    render(<PlanDetail plan={makePlan({ leave_type_name: "Annual Leave" })} />);
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getByText("Upcoming")).toBeInTheDocument();
    expect(screen.getByText(/2 Nov 2026/)).toBeInTheDocument();
  });

  it("offers Apply Now for a live plan and hands off to the draft editor", async () => {
    vi.mocked(applyPlan).mockResolvedValue({ application_id: "draft-3" });
    render(<PlanDetail plan={makePlan({ id: "plan-5", status: "notified" })} />);

    fireEvent.click(screen.getByRole("button", { name: /apply now/i }));

    await waitFor(() => expect(applyPlan).toHaveBeenCalledWith("plan-5"));
    expect(push).toHaveBeenCalledWith("/dashboard/leave/drafts?edit=draft-3");
  });

  it("reports an apply failure without navigating", async () => {
    vi.mocked(applyPlan).mockRejectedValue(new Error("This plan has already been applied."));
    render(<PlanDetail plan={makePlan({ status: "notified" })} />);

    fireEvent.click(screen.getByRole("button", { name: /apply now/i }));

    expect(
      await screen.findByText("This plan has already been applied.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("offers to reopen the draft for a converted plan", () => {
    render(
      <PlanDetail
        plan={makePlan({ status: "converted", converted_application: "draft-9" })}
      />
    );
    expect(screen.queryByRole("button", { name: /apply now/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /open the draft/i }));
    expect(push).toHaveBeenCalledWith("/dashboard/leave/drafts?edit=draft-9");
  });

  it("offers a fresh plan for a missed one, keeping the leave type", () => {
    render(<PlanDetail plan={makePlan({ status: "missed", leave_type_id: 4 })} />);
    fireEvent.click(screen.getByRole("button", { name: /plan for different dates/i }));
    expect(push).toHaveBeenCalledWith("/dashboard/plans/new?leaveType=4");
  });

  it("shows no actions for a cancelled plan", () => {
    render(<PlanDetail plan={makePlan({ status: "cancelled" })} />);
    expect(screen.queryByRole("button", { name: /apply now/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open the draft/i })).not.toBeInTheDocument();
  });
});
