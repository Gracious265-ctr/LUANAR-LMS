import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { format, parseISO } from "date-fns";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PlansWorkspace } from "@/components/plans/plans-workspace";
import { makeDraftDetail } from "@/lib/plans/__fixtures__";
import { selectOption } from "./helpers/select";

/** October 2026 is the calendar's default month, so day lookups are stable. */
const TODAY = new Date(2026, 9, 5);

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/dashboard/plans" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

// The list panels fetch their own data; the overlay is what is under test.
vi.mock("@/components/plans/plans-list", () => ({ PlansList: () => null }));
vi.mock("@/components/plans/plan-approvals-list", () => ({
  PlanApprovalsList: () => null,
}));
vi.mock("@/components/plans/plan-confirmations-panel", () => ({
  PlanConfirmationsPanel: () => null,
}));

function dayButton(iso: string): HTMLElement {
  return within(screen.getByRole("grid")).getByRole("button", {
    name: format(parseISO(iso), "PPPP"),
  });
}

function chooseRange(name: string | RegExp, from: string, to: string) {
  fireEvent.click(screen.getByRole("button", { name }));
  fireEvent.click(dayButton(from));
  fireEvent.click(dayButton(to));
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("PlansWorkspace plan overlay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(TODAY);
    pathnameRef.current = "/dashboard/plans";
    searchParamsRef.current = new URLSearchParams();

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/leave/leave-types/")) {
          return Promise.resolve(
            jsonResponse([{ id: 1, name: "Annual leave", code: "annual" }])
          );
        }
        return Promise.resolve(jsonResponse(makeDraftDetail()));
      })
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("renders the workspace with no overlay open", () => {
    render(<PlansWorkspace />);

    expect(
      screen.getByRole("button", { name: /New plan/ })
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens the create form from the trigger", () => {
    render(<PlansWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /New plan/ }));

    expect(routerMock.push).toHaveBeenCalledWith("/dashboard/plans?plan=new");
  });

  it("reopens the create form from the URL alone, so a refresh resumes it", async () => {
    searchParamsRef.current = new URLSearchParams("plan=new");
    render(<PlansWorkspace />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      await screen.findByRole("combobox", { name: "Leave type (block 1)" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeInTheDocument();
  });

  it("closes on cancel without writing anything", async () => {
    searchParamsRef.current = new URLSearchParams("plan=new");
    render(<PlansWorkspace />);
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // Cancel is a button here, not a link: the overlay owns dismissal. The
    // lone JSDOM history entry takes close's replace fallback.
    expect(routerMock.replace).toHaveBeenCalledWith("/dashboard/plans");
    expect(routerMock.push).not.toHaveBeenCalled();
    // The dialog itself only disappears once the mocked router feeds the
    // cleared URL back in, which is the real navigation's job.
  });

  it("swaps the overlay URL for the new plan's page after a save", async () => {
    searchParamsRef.current = new URLSearchParams("plan=new");
    render(<PlansWorkspace />);
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    chooseRange("Period covered", "2026-10-01", "2026-10-30");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 1)" }),
      "Annual leave"
    );
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    // `replace`, not `push`: the overlay's own history entry is the one being
    // swapped for the plan, so Back from the plan lands on the list rather
    // than on an empty create form.
    await waitFor(() =>
      expect(routerMock.replace).toHaveBeenCalledWith("/dashboard/plans/plan-1")
    );
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  it("leaves the overlay open and shows the reason when the save fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/leave/leave-types/")) {
          return Promise.resolve(
            jsonResponse([{ id: 1, name: "Annual leave", code: "annual" }])
          );
        }
        return Promise.resolve(
          jsonResponse({ detail: "Block overlaps another plan." }, 400)
        );
      })
    );
    searchParamsRef.current = new URLSearchParams("plan=new");
    render(<PlansWorkspace />);
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    chooseRange("Period covered", "2026-10-01", "2026-10-30");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 1)" }),
      "Annual leave"
    );
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText("Block overlaps another plan.")
    ).toBeInTheDocument();
    expect(routerMock.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
