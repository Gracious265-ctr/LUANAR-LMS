import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CancellationDetailPanel } from "@/components/cancellations/cancellation-detail-panel";
import { makeApprovedRequest, makeDetail } from "@/lib/cancellations/__fixtures__";
import type { CancellationDetail } from "@/lib/cancellations/types";
import {
  fetchCancellationDetail,
  postCancellationDecision,
} from "@/lib/cancellations/service";
import { Toaster } from "@/components/ui/toast";

vi.mock("@/lib/cancellations/service", () => ({
  fetchCancellationDetail: vi.fn(),
  postCancellationDecision: vi.fn(),
}));

const mockedFetchDetail = vi.mocked(fetchCancellationDetail);
const mockedPostDecision = vi.mocked(postCancellationDecision);

function detailWithBalance(detail: Partial<CancellationDetail> = {}) {
  return makeDetail({
    requested_by_name: "Chikondi Mbewe",
    balance_impact: { restore_days: "10.0", restore_financial_year: "2026-27" },
    ...detail,
  });
}

/** Match against an element's full normalized textContent (handles nested <span>). */
const textContent =
  (expected: string) => (_content: string, el: Element | null) =>
    el?.textContent?.replace(/\s+/g, " ").trim() === expected;

function renderPanel(overrides: { onApplicationChanged?: () => void } = {}) {
  // The panel reports every outcome through the global toast stack (spec 3.5),
  // so the Toaster has to be mounted for those messages to be findable.
  return render(
    <>
      <CancellationDetailPanel
        requestId="canc-1"
        onApplicationChanged={overrides.onApplicationChanged ?? vi.fn()}
      />
      <Toaster />
    </>
  );
}

describe("CancellationDetailPanel", () => {
  it("shows requester, reason, original leave, balance impact and stages", async () => {
    mockedFetchDetail.mockResolvedValue({ ok: true, data: detailWithBalance() });
    renderPanel();

    expect(await screen.findByText("Chikondi Mbewe")).toBeInTheDocument();
    expect(
      screen.getByText("The university rescheduled my teaching block.")
    ).toBeInTheDocument();
    expect(screen.getByText("LV-2026-27-800123")).toBeInTheDocument();
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getByText(/10 working · 12 calendar/)).toBeInTheDocument();
    expect(screen.getByText(/Approving restores/)).toBeInTheDocument();
    const stepper = screen.getByLabelText("Cancellation approval progress");
    expect(within(stepper).getByText("Supervisor")).toBeInTheDocument();
    expect(within(stepper).getByText("HOD")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("shows the leave-started warning and disables approve", async () => {
    mockedFetchDetail.mockResolvedValue({
      ok: true,
      data: detailWithBalance({ leave_started: true }),
    });
    renderPanel();

    expect(await screen.findByText("Pending approval")).toBeInTheDocument();
    expect(
      screen.getByText("Leave has started; this request can only be rejected.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("records an approve decision and notifies the parent", async () => {
    mockedFetchDetail.mockResolvedValue({ ok: true, data: detailWithBalance() });
    mockedPostDecision.mockResolvedValue({
      ok: true,
      data: detailWithBalance({
        request: makeApprovedRequest({ id: "canc-1" }),
        can_decide: false,
      }),
    });
    const onApplicationChanged = vi.fn();
    renderPanel({ onApplicationChanged });

    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /^Approve$/ }));

    await waitFor(() => expect(mockedPostDecision).toHaveBeenCalled());
    expect(mockedPostDecision.mock.calls[0][0]).toBe("canc-1");
    expect(mockedPostDecision.mock.calls[0][1]).toEqual({
      decision: "approve",
      comment: "",
      stage_version: 1,
    });

    expect(await screen.findByText("Cancellation approved.")).toBeInTheDocument();
    expect(onApplicationChanged).toHaveBeenCalled();
  });

  it("blocks a reject without a comment", async () => {
    mockedFetchDetail.mockResolvedValue({ ok: true, data: detailWithBalance() });
    renderPanel();

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: /^Reject$/ });
    expect(confirm).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), {
      target: { value: "Leave was already staffed" },
    });
    expect(await within(dialog).findByText("25 / 1000")).toBeInTheDocument();
    expect(confirm).toBeEnabled();

    mockedPostDecision.mockResolvedValue({
      ok: true,
      data: detailWithBalance({ can_decide: false }),
    });
    fireEvent.click(confirm);
    await waitFor(() => expect(mockedPostDecision).toHaveBeenCalled());
    expect(
      mockedPostDecision.mock.calls[0][1]
    ).toEqual({
      decision: "reject",
      comment: "Leave was already staffed",
      stage_version: 1,
    });
  });

  it("shows a read-only summary when the viewer cannot decide", async () => {
    mockedFetchDetail.mockResolvedValue({
      ok: true,
      data: detailWithBalance({
        can_decide: false,
        my_decision: {
          decision: "approved",
          decided_at: "2026-10-15T14:22:19Z",
          comment: "Approved.",
        },
      }),
    });
    renderPanel();

    expect(
      await screen.findByText(
        textContent("You approved this cancellation on 15 Oct 2026, 16:22.")
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve" })
    ).not.toBeInTheDocument();
  });

  it("shows the refresh toast and refetches on a 409 conflict", async () => {
    mockedFetchDetail.mockResolvedValue({ ok: true, data: detailWithBalance() });
    mockedPostDecision.mockResolvedValue({
      ok: false,
      kind: "conflict",
      code: "stale_stage_version",
      message: "This request has changed since you opened it.",
    });
    renderPanel();

    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: /^Approve$/ })
    );

    expect(
      await screen.findByText("This request changed. Refreshing…")
    ).toBeInTheDocument();
    await waitFor(() => expect(mockedPostDecision).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedFetchDetail).toHaveBeenCalledTimes(2));
  });

  it("renders nothing when the request id does not resolve", async () => {
    mockedFetchDetail.mockResolvedValue({
      ok: false,
      kind: "not_found",
      message: "Cancellation request not found.",
    });
    const { container } = renderPanel();
    await waitFor(() => expect(mockedFetchDetail).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });
});