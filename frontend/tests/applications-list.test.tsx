import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationsList } from "@/components/leave/ApplicationsList";
import type { LeaveApplication } from "@/lib/leave-api";
import { getLeaveApplications } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";

vi.mock("@/lib/leave-api", () => ({
  getLeaveApplications: vi.fn(),
  deleteLeaveApplication: vi.fn(),
}));

vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));

const { pushMock, replaceMock, backMock, searchParamsMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
  backMock: vi.fn(),
  searchParamsMock: { current: new URLSearchParams() },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/leave/drafts",
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
    back: backMock,
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => searchParamsMock.current,
}));

import { deleteLeaveApplication } from "@/lib/leave-api";

/** Sets the query string the overlay reads its open state from. */
function setSearchParams(query: string) {
  searchParamsMock.current = new URLSearchParams(query);
}

function makeApplication(
  over: Partial<LeaveApplication> = {}
): LeaveApplication {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-10-01",
    end_date: "2026-10-05",
    calculated_days: 3,
    working_days: 3,
    calendar_days: 5,
    financial_year_label: "2026-27",
    reason: "Family visit",
    status: "draft",
    reference_number: null,
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    submitted_at: null,
    documents: [],
    ...over,
  };
}

describe("ApplicationsList (My Applications)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setSearchParams("");
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
  });

  it("excludes drafts and applies no status filter by default", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [
        makeApplication({
          id: "submitted-1",
          status: "submitted",
          reference_number: "LV-2026-27-000001",
          submitted_at: "2026-09-21T10:00:00Z",
        }),
      ],
    });

    render(<ApplicationsList view="applications" />);

    expect(await screen.findByText("My Applications")).toBeInTheDocument();
    expect(getLeaveApplications).toHaveBeenCalledWith({
      status: undefined,
      excludeStatus: "draft",
    });
    expect(screen.getByText("1 application")).toBeInTheDocument();
    expect(screen.getByText("LV-2026-27-000001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Track this application" })).toHaveAttribute(
      "href",
      "/applications/submitted-1"
    );
  });

  it("passes the ?status= filter through to the API", async () => {
    setSearchParams("status=submitted");
    vi.mocked(getLeaveApplications).mockResolvedValue({ count: 0, results: [] });

    render(<ApplicationsList view="applications" />);

    expect(await screen.findByText("My Applications")).toBeInTheDocument();
    expect(getLeaveApplications).toHaveBeenCalledWith({
      status: "submitted",
      excludeStatus: "draft",
    });
  });

  it("renders the empty state when there are no applications", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({ count: 0, results: [] });

    render(<ApplicationsList view="applications" />);

    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
    expect(screen.getByText("0 applications")).toBeInTheDocument();
  });

  it("shows the error state and retries", async () => {
    vi.mocked(getLeaveApplications).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [makeApplication({ id: "submitted-1", status: "submitted" })],
    });

    render(<ApplicationsList view="applications" />);

    const error = await screen.findByText("boom");
    expect(error).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByRole("link", { name: "Track this application" })).toBeInTheDocument();
  });
});

describe("ApplicationsList (Drafts)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setSearchParams("");
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
  });

  it("asks the API only for drafts", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [makeApplication({ id: "draft-1", status: "draft" })],
    });

    render(<ApplicationsList view="drafts" />);

    expect(await screen.findByText("Drafts")).toBeInTheDocument();
    expect(getLeaveApplications).toHaveBeenCalledWith({ status: "draft" });
  });

  it("removes the draft optimistically without refetching", async () => {
    vi.mocked(deleteLeaveApplication).mockResolvedValue(undefined);
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 2,
      results: [
        makeApplication({ id: "submitted-1", status: "submitted" }),
        makeApplication({ id: "draft-1", status: "draft" }),
      ],
    });

    render(<ApplicationsList view="drafts" />);

    const deleteButton = await screen.findByRole("button", { name: "Delete draft" });
    fireEvent.click(deleteButton);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    // The row leaves as soon as the delete is dispatched — no skeleton flash
    // and no extra list round trip (spec 3.5).
    expect(
      screen.queryByRole("button", { name: "Delete draft" })
    ).not.toBeInTheDocument();
    expect(deleteLeaveApplication).toHaveBeenCalledWith("draft-1");
    expect(getLeaveApplications).toHaveBeenCalledTimes(1);
  });

  it("resumes the most recently edited draft for a compose request", async () => {
    setSearchParams("compose=1");
    const fetchSpy = vi
      .fn()
      .mockResolvedValue({ ok: false, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchSpy);
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 2,
      results: [
        makeApplication({
          id: "older-1",
          status: "draft",
          updated_at: "2026-09-19T10:00:00Z",
        }),
        makeApplication({
          id: "newer-1",
          status: "draft",
          updated_at: "2026-09-25T10:00:00Z",
        }),
      ],
    });

    render(<ApplicationsList view="drafts" />);

    // The overlay opens on the newest draft rather than a blank create form.
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/leave/leave-applications/newer-1/"),
      expect.anything()
    );
    vi.unstubAllGlobals();
  });
});

describe("ApplicationsList overlay entry points", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setSearchParams("");
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
    ]);
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [makeApplication({ id: "draft-1", status: "draft" })],
    });
  });

  it("opens a new application in the overlay instead of navigating away", async () => {
    render(<ApplicationsList view="drafts" />);
    await screen.findByText("Drafts");

    fireEvent.click(screen.getByRole("button", { name: /new application/i }));

    expect(pushMock).toHaveBeenCalledWith("/dashboard/leave/drafts?compose=1");
  });

  it("opens an existing draft in the overlay from the card's Edit action", async () => {
    render(<ApplicationsList view="drafts" />);
    await screen.findByText("Drafts");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(pushMock).toHaveBeenCalledWith("/dashboard/leave/drafts?edit=draft-1");
  });

  it("opens the review stage directly from the card's Review action", async () => {
    render(<ApplicationsList view="drafts" />);
    await screen.findByText("Drafts");

    fireEvent.click(screen.getByRole("button", { name: "Review" }));

    expect(pushMock).toHaveBeenCalledWith(
      "/dashboard/leave/drafts?edit=draft-1&stage=review"
    );
  });

  it("disables Review until the draft is complete", async () => {
    vi.mocked(getLeaveApplications).mockResolvedValue({
      count: 1,
      results: [
        makeApplication({ id: "draft-1", status: "draft", reason: "" }),
      ],
    });

    render(<ApplicationsList view="drafts" />);
    await screen.findByText("Drafts");

    expect(screen.getByRole("button", { name: "Review" })).toBeDisabled();
  });

  it("does not render an overlay without a compose or edit param", async () => {
    render(<ApplicationsList view="drafts" />);
    await screen.findByText("Drafts");

    expect(
      screen.queryByRole("dialog")
    ).not.toBeInTheDocument();
  });
});
