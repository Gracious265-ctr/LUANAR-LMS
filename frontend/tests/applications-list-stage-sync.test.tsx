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
  usePathname: () => "/leave/drafts",
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

/**
 * The overlay is stubbed so the tests can drive stage transitions directly.
 * The real dialog is covered in leave-application-overlay.test.tsx; what matters
 * here is the host's contract with it, which is the URL rewrite.
 */
vi.mock("@/components/leave/LeaveApplicationOverlay", () => ({
  LeaveApplicationOverlay: ({
    initialStage,
    onStageChange,
    onOpenChange,
  }: {
    initialStage?: string;
    onStageChange?: (stage: string, applicationId?: string) => void;
    onOpenChange: (open: boolean) => void;
  }) => (
    <div>
      <span data-testid="stage">{initialStage ?? "form"}</span>
      <button
        onClick={() => onStageChange?.("review", "draft-9")}
        type="button"
      >
        to review
      </button>
      <button
        onClick={() => onStageChange?.("done", "draft-9")}
        type="button"
      >
        to done
      </button>
      <button onClick={() => onStageChange?.("form", "draft-9")} type="button">
        to form
      </button>
      <button onClick={() => onOpenChange(false)} type="button">
        close
      </button>
    </div>
  ),
}));

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

beforeEach(() => {
  vi.clearAllMocks();
  searchParamsMock.current = new URLSearchParams();
  vi.mocked(getLeaveTypes).mockResolvedValue([
    { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
  ]);
  vi.mocked(getLeaveApplications).mockResolvedValue({
    count: 1,
    results: [makeApplication({ id: "draft-1", status: "draft" })],
  });
  // JSDOM only lets `history.length` grow within a test file and `replaceState`
  // cannot truncate it, so the Back branch has to be forced directly.
  vi.stubGlobal("history", { ...window.history, length: 2 });
});

describe("ApplicationsList stage URL sync", () => {
  it("mirrors a move to review into the URL", async () => {
    setSearchParams("edit=draft-1&stage=form");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "to review" }));

    expect(replaceMock).toHaveBeenCalledWith(
      "/leave/drafts?edit=draft-9&stage=review"
    );
  });

  it("mirrors a move to the confirmation stage into the URL", async () => {
    setSearchParams("edit=draft-1&stage=review");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "to done" }));

    expect(replaceMock).toHaveBeenCalledWith(
      "/leave/drafts?edit=draft-9&stage=done"
    );
  });

  it("drops the stage param when stepping back to the form", async () => {
    setSearchParams("edit=draft-1&stage=review");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "to form" }));

    expect(replaceMock).toHaveBeenCalledWith(
      "/leave/drafts?edit=draft-9"
    );
  });

  it("uses the reported id for a create flow, which has no target yet", async () => {
    setSearchParams("compose=1");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "to review" }));

    // `?compose=1` carries no application id, so without the reported one the
    // URL could not name the draft the user just created.
    expect(replaceMock).toHaveBeenCalledWith(
      "/leave/drafts?edit=draft-9&stage=review"
    );
  });

  it("replaces rather than pushes, so one close still exits the overlay", async () => {
    setSearchParams("edit=draft-1&stage=form");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "to review" }));
    fireEvent.click(screen.getByRole("button", { name: "to done" }));
    fireEvent.click(screen.getByRole("button", { name: "close" }));

    // A push per stage would leave the user inside the dialog after closing it,
    // one Back press per stage visited.
    expect(pushMock).not.toHaveBeenCalled();
    expect(backMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to replace on a direct visit with nothing to go back to", async () => {
    vi.stubGlobal("history", { ...window.history, length: 1 });
    setSearchParams("edit=draft-1&stage=review");
    render(<ApplicationsList />);
    await screen.findByText("My Applications");

    fireEvent.click(screen.getByRole("button", { name: "close" }));

    expect(backMock).not.toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/leave/drafts");
  });
});
