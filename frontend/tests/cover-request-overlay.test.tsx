import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CoverRequestSection } from "@/components/approvals/CoverRequestSection";
import type { DelegateCandidate, Delegation } from "@/lib/delegations";
import { createDelegation } from "@/lib/delegations-client";

import { pickRangeStart } from "./helpers/date";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/approvals/cover" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return { ...actual, createDelegation: vi.fn() };
});

const candidates: DelegateCandidate[] = [
  { id: 5, full_name: "Bob HOD", role: "approver" },
];

function makeDelegation(over: Partial<Delegation> = {}): Delegation {
  return {
    id: 9,
    approver: 3,
    approver_name: "Jane Dean",
    approver_role: "dean",
    delegate: 5,
    delegate_name: "Bob HOD",
    starts_on: "2026-10-01",
    ends_on: "2026-11-01",
    request_reason: "On study leave",
    requested_by: 3,
    requested_by_name: "Jane Dean",
    decision_reason: "",
    decided_by: null,
    decided_at: null,
    status: "requested",
    state: "requested",
    created_at: "2026-09-26T12:00:00Z",
    updated_at: "2026-09-26T12:00:00Z",
    ...over,
  };
}

describe("CoverRequestSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    pathnameRef.current = "/approvals/cover";
    vi.mocked(createDelegation).mockResolvedValue(makeDelegation());
    // JSDOM starts with a single history entry, so the `> 1` guard in `close`
    // would otherwise fall through to `replace` in every test.
    window.history.replaceState({}, "", "/approvals/cover");
  });

  it("shows a trigger rather than the inline form", () => {
    render(<CoverRequestSection candidates={candidates} />);

    expect(
      screen.getByRole("button", { name: /Request cover/ })
    ).toBeInTheDocument();
    expect(screen.queryByTestId("cover-request-form")).toBeNull();
  });

  it("opens the overlay from the cover query parameter", () => {
    searchParamsRef.current = new URLSearchParams("cover=new");
    render(<CoverRequestSection candidates={candidates} />);

    expect(screen.getByTestId("cover-request-form")).toBeInTheDocument();
  });

  it("stays closed when the query parameter is absent", () => {
    render(<CoverRequestSection candidates={candidates} />);

    expect(screen.queryByTestId("cover-request-form")).toBeNull();
  });

  it("pushes the query parameter when the trigger is used", () => {
    render(<CoverRequestSection candidates={candidates} />);

    fireEvent.click(screen.getByRole("button", { name: /Request cover/ }));

    expect(routerMock.push).toHaveBeenCalledWith("/approvals/cover?cover=new");
  });

  it("preserves the approvals tab when opening from the shared panel", () => {
    pathnameRef.current = "/approvals";
    searchParamsRef.current = new URLSearchParams("view=cover");
    render(<CoverRequestSection candidates={candidates} />);

    fireEvent.click(screen.getByRole("button", { name: /Request cover/ }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/approvals?view=cover&cover=new"
    );
  });

  it("refetches and closes when the confirmation is acknowledged", async () => {
    searchParamsRef.current = new URLSearchParams("cover=new");
    render(<CoverRequestSection candidates={candidates} />);

    pickRangeStart(screen.getByLabelText("Period"), "2026-10-01");
    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    expect(await screen.findByText("Cover requested")).toBeInTheDocument();
    expect(screen.getByText(/Bob HOD nominated/)).toBeInTheDocument();
    // The close affordance is gone on the confirmation so it cannot be
    // dismissed without acknowledging the request.
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(routerMock.refresh).toHaveBeenCalled();
    // JSDOM starts a test with a single history entry, so this exercises the
    // direct-visit fallback in `close` rather than the `router.back()` path.
    expect(routerMock.replace).toHaveBeenCalledWith("/approvals/cover");
  });

  it("surfaces a rejection inside the overlay rather than behind it", async () => {
    vi.mocked(createDelegation).mockRejectedValue(
      new Error("approver: This approver already has an open delegation request.")
    );
    searchParamsRef.current = new URLSearchParams("cover=new");
    render(<CoverRequestSection candidates={candidates} />);

    pickRangeStart(screen.getByLabelText("Period"), "2026-10-01");
    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("already has an open delegation request");
    expect(screen.queryByText("Cover requested")).toBeNull();
    expect(routerMock.refresh).not.toHaveBeenCalled();
  });

  it("returns to a blank form after a completed request", async () => {
    searchParamsRef.current = new URLSearchParams("cover=new");
    const { rerender } = render(<CoverRequestSection candidates={candidates} />);

    pickRangeStart(screen.getByLabelText("Period"), "2026-10-01");
    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));
    await screen.findByText("Cover requested");

    // Closing and reopening must not resurrect the previous confirmation; the
    // state has to be discarded with the dialog.
    searchParamsRef.current = new URLSearchParams();
    rerender(<CoverRequestSection candidates={candidates} />);
    expect(screen.queryByText("Cover requested")).toBeNull();

    searchParamsRef.current = new URLSearchParams("cover=new");
    rerender(<CoverRequestSection candidates={candidates} />);

    expect(screen.getByTestId("cover-request-form")).toBeInTheDocument();
    expect(screen.getByLabelText("Period")).toHaveTextContent("Select date range");
  });

  it("requires a start date before submitting", async () => {
    searchParamsRef.current = new URLSearchParams("cover=new");
    render(<CoverRequestSection candidates={candidates} />);

    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Choose a start date."
    );
    expect(createDelegation).not.toHaveBeenCalled();
  });

  it("closes on the cancel button without submitting", async () => {
    searchParamsRef.current = new URLSearchParams("cover=new");
    render(<CoverRequestSection candidates={candidates} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(routerMock.replace).toHaveBeenCalledWith("/approvals/cover")
    );
    expect(createDelegation).not.toHaveBeenCalled();
  });
});
