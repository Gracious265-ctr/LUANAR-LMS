import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeaveDashboardPage from "@/app/(dashboard)/dashboard/leave/page";
import { useLeaveDashboard } from "@/lib/hooks/useLeaveDashboard";
import type { LeaveApplicationSummary, LeaveDashboardData } from "@/lib/leave-dashboard";

vi.mock("@/lib/hooks/useLeaveDashboard", () => ({
  useLeaveDashboard: vi.fn(),
}));

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

function summary(
  over: Partial<LeaveApplicationSummary> = {}
): LeaveApplicationSummary {
  return {
    id: "app-1",
    leave_type: "Annual Leave",
    start_date: "2026-11-03",
    end_date: "2026-11-07",
    status: "pending",
    last_comment_excerpt: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-02T09:00:00Z",
    ...over,
  };
}

function data(over: Partial<LeaveDashboardData> = {}): LeaveDashboardData {
  return {
    balances: [{ leave_type: "Annual Leave", used: 9, total: 21 }],
    pending_count: 0,
    upcoming_leave: null,
    needs_attention: [],
    drafts: [],
    recent: [],
    ...over,
  };
}

function mockDashboard(result: {
  data?: LeaveDashboardData | null;
  isLoading?: boolean;
  error?: string | null;
  refetch?: () => Promise<void>;
}) {
  vi.mocked(useLeaveDashboard).mockReturnValue({
    data: result.data ?? null,
    isLoading: result.isLoading ?? false,
    error: result.error ?? null,
    refetch: result.refetch ?? vi.fn(async () => {}),
  });
}

describe("LeaveDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the header, balance rings and all populated sections", () => {
    mockDashboard({
      data: data({
        needs_attention: [
          summary({
            id: "rej-1",
            status: "rejected",
            last_comment_excerpt: "Not enough notice.",
          }),
        ],
        recent: [summary({ id: "recent-1", status: "approved" })],
      }),
    });

    render(<LeaveDashboardPage />);

    expect(
      screen.getByRole("heading", { name: "Leave Applications" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Your Balance" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Needs Your Attention" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Recent Applications" })
    ).toBeInTheDocument();
    expect(screen.getByText("9 of 21 days used")).toBeInTheDocument();
    expect(screen.getByText(/Not enough notice\./)).toBeInTheDocument();
  });

  it("presents the balance figures as a card rather than loose in the rail", () => {
    // The rail answers one question — how much leave is left — so the heading
    // and its rings are one panel, drawn with the design system's card surface,
    // instead of a heading floating above uncontained rings.
    mockDashboard({ data: data() });

    render(<LeaveDashboardPage />);

    const card = screen.getByRole("heading", { name: "Your Balance" })
      .parentElement;
    expect(card).toHaveClass("bg-surface-card");
    expect(card).toHaveClass("shadow-card");
  });

  it("hides the needs-attention section when empty", () => {
    mockDashboard({ data: data() });

    render(<LeaveDashboardPage />);

    expect(
      screen.queryByRole("heading", { name: "Needs Your Attention" })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Recent Applications" })
    ).toBeInTheDocument();
  });

  it("shows an empty state when the employee has no applications", () => {
    mockDashboard({ data: data() });

    render(<LeaveDashboardPage />);

    expect(screen.getByText("No applications yet")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New Application" }));
    expect(pushMock).toHaveBeenCalledWith("/dashboard/leave/drafts?compose=1");
  });

  it("renders a dashboard-shaped skeleton while loading", () => {
    mockDashboard({ isLoading: true });

    render(<LeaveDashboardPage />);

    const region = screen.getByRole("status", {
      name: "Loading your leave dashboard",
    });
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(
      screen.queryByRole("heading", { name: "Leave Applications" })
    ).toBeInTheDocument();
  });

  it("offers a working Retry on error", () => {
    const refetch = vi.fn(async () => {});
    mockDashboard({ error: "Failed to load your dashboard", refetch });

    render(<LeaveDashboardPage />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Couldn't load your dashboard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("leaves the create action to the sidebar, not the page header", () => {
    // The header's "+ New Application" button was removed, so a dashboard with
    // applications on it opens on its figures rather than a second copy of an
    // action the sidebar already offers (/dashboard/leave/new). The empty state
    // below still carries it for an employee who has nothing yet.
    mockDashboard({ data: data({ recent: [summary({ id: "recent-1" })] }) });

    render(<LeaveDashboardPage />);

    expect(
      screen.queryByRole("button", { name: /New Application/ })
    ).not.toBeInTheDocument();
  });

  it("routes a needs-attention card straight to the edit overlay", () => {
    mockDashboard({
      data: data({ needs_attention: [summary({ id: "fix-1", status: "rejected" })] }),
    });

    render(<LeaveDashboardPage />);

    fireEvent.click(screen.getByRole("button", { name: /Rejected/ }));
    expect(pushMock).toHaveBeenCalledWith(
      "/dashboard/leave/applications?edit=fix-1"
    );
  });

  it("routes a recent row to the tracking page and links View all", () => {
    mockDashboard({
      data: data({ recent: [summary({ id: "recent-9", status: "approved" })] }),
    });

    render(<LeaveDashboardPage />);

    fireEvent.click(screen.getByRole("link", { name: /Annual Leave/ }));
    expect(pushMock).toHaveBeenCalledWith("/applications/recent-9");
    expect(screen.getByRole("link", { name: /View all/ })).toHaveAttribute(
      "href",
      "/dashboard/leave/applications"
    );
  });

  it("shows the pending and upcoming stat cards above everything else", () => {
    mockDashboard({
      data: data({
        pending_count: 3,
        upcoming_leave: {
          id: "up-1",
          leave_type: "Annual Leave",
          start_date: "2026-11-03",
          end_date: "2026-11-07",
          days_until: 5,
        },
      }),
    });

    render(<LeaveDashboardPage />);

    expect(screen.getByText("Pending Applications")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("awaiting review")).toBeInTheDocument();
    expect(screen.getByText("Upcoming Leave")).toBeInTheDocument();
    expect(screen.getByText("in 5 days")).toBeInTheDocument();
    expect(
      screen.getByText("03 Nov 2026 – 07 Nov 2026, Annual Leave")
    ).toBeInTheDocument();
  });

  it("routes the pending card to My Applications filtered to pending", () => {
    mockDashboard({ data: data({ pending_count: 2 }) });

    render(<LeaveDashboardPage />);

    fireEvent.click(
      screen.getByRole("button", { name: /Pending Applications/ })
    );
    expect(pushMock).toHaveBeenCalledWith(
      "/dashboard/leave/applications?status=submitted"
    );
  });

  it("routes the upcoming card to that application's tracking page", () => {
    mockDashboard({
      data: data({
        upcoming_leave: {
          id: "up-9",
          leave_type: "Sick Leave",
          start_date: "2026-11-03",
          end_date: "2026-11-04",
          days_until: 1,
        },
      }),
    });

    render(<LeaveDashboardPage />);

    expect(screen.getByText("in 1 day")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Upcoming Leave/ }));
    expect(pushMock).toHaveBeenCalledWith("/applications/up-9");
  });

  it("shows an em dash and no clickable card when no leave is upcoming", () => {
    mockDashboard({ data: data({ upcoming_leave: null }) });

    render(<LeaveDashboardPage />);

    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("No upcoming leave scheduled")).toBeInTheDocument();
    // Nothing to navigate to, so it must not be a control.
    expect(
      screen.queryByRole("button", { name: /Upcoming Leave/ })
    ).not.toBeInTheDocument();
  });
});
