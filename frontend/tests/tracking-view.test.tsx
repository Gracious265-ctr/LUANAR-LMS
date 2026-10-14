import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TrackingView } from "@/components/tracking/TrackingView";
import { fetchTracking } from "@/lib/tracking/service";
import type { TrackingResponse, TrackingResult } from "@/lib/tracking/types";

vi.mock("@/lib/tracking/service", () => ({
  fetchTracking: vi.fn(),
}));

<<<<<<< HEAD
vi.mock("@/lib/cancellation/service", () => ({
  fetchCancellations: vi.fn(),
}));

import { fetchCancellations } from "@/lib/cancellation/service";

=======
vi.mock("@/lib/leave-api", () => ({
  listDocuments: vi.fn(),
}));

>>>>>>> feature/plans-teams
import approved from "@/lib/tracking/__fixtures__/approved.json";
import cancelled from "@/lib/tracking/__fixtures__/cancelled.json";
import correction_required_at_stage_3 from "@/lib/tracking/__fixtures__/correction_required_at_stage_3.json";
import pending_first_stage from "@/lib/tracking/__fixtures__/pending_first_stage.json";
import pending_mid_workflow from "@/lib/tracking/__fixtures__/pending_mid_workflow.json";
import pending_with_applicant_excluded from "@/lib/tracking/__fixtures__/pending_with_applicant_excluded.json";
import pending_with_skipped_stage from "@/lib/tracking/__fixtures__/pending_with_skipped_stage.json";
import pending_with_delegate from "@/lib/tracking/__fixtures__/pending_with_delegate.json";
import rejected_at_stage_2 from "@/lib/tracking/__fixtures__/rejected_at_stage_2.json";
import resubmitted_after_correction from "@/lib/tracking/__fixtures__/resubmitted_after_correction.json";
import resubmitted_after_rejection from "@/lib/tracking/__fixtures__/resubmitted_after_rejection.json";
import { listDocuments } from "@/lib/leave-api";

const fixtures: Record<string, TrackingResponse> = {
  "pending_first_stage": pending_first_stage as unknown as TrackingResponse,
  "pending_mid_workflow": pending_mid_workflow as unknown as TrackingResponse,
  "pending_with_delegate": pending_with_delegate as unknown as TrackingResponse,
  "pending_with_applicant_excluded":
    pending_with_applicant_excluded as unknown as TrackingResponse,
  "pending_with_skipped_stage":
    pending_with_skipped_stage as unknown as TrackingResponse,
  "approved": approved as unknown as TrackingResponse,
  "rejected_at_stage_2": rejected_at_stage_2 as unknown as TrackingResponse,
  "correction_required_at_stage_3":
    correction_required_at_stage_3 as unknown as TrackingResponse,
  "resubmitted_after_correction":
    resubmitted_after_correction as unknown as TrackingResponse,
  "resubmitted_after_rejection":
    resubmitted_after_rejection as unknown as TrackingResponse,
  "cancelled": cancelled as unknown as TrackingResponse,
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/** Match against an element's full normalized textContent (handles nested <strong>/<time>). */
const textContent =
  (expected: string) => (_content: string, el: Element | null) =>
    el?.textContent?.replace(/\s+/g, " ").trim() === expected;

function mockOk(data: TrackingResponse) {
  vi.mocked(fetchTracking).mockResolvedValue({
    ok: true,
    data,
  } satisfies TrackingResult);
}

function renderView(id = "app-1") {
  return render(<TrackingView applicationId={id} />);
}

const stepCount = () =>
  document.querySelectorAll('[aria-current="step"]').length;

beforeEach(() => {
  vi.clearAllMocks();
<<<<<<< HEAD
  vi.mocked(fetchCancellations).mockResolvedValue([]);
=======
  vi.mocked(listDocuments).mockResolvedValue([]);
>>>>>>> feature/plans-teams
});

describe("TrackingView · header", () => {
  it("renders reference, badge, leave type, dates, days and submitted time", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();

    expect(await screen.findByText("LV-2026-27-900001")).toBeInTheDocument();
    expect(screen.getByText("Pending Approval")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Annual Leave · 2 Nov 2026 – 6 Nov 2026 · 5 working days"
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/Submitted/)).toBeInTheDocument();
    expect(screen.getByText("My applications")).toBeInTheDocument();
  });

  it("refreshes on demand and shows the last-refreshed time", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();
    await screen.findByText("Pending Approval");

    const button = screen.getByRole("button", { name: "Refresh" });
    await waitFor(() => expect(fetchTracking).toHaveBeenCalledTimes(1));
    button.click();
    await waitFor(() => expect(fetchTracking).toHaveBeenCalledTimes(2));
    expect(screen.getByText(/Last refreshed/)).toBeInTheDocument();
  });
});

describe("TrackingView · statuses", () => {
  it.each([
    ["pending_first_stage", "Pending Approval"],
    ["pending_mid_workflow", "Pending Approval"],
    ["pending_with_delegate", "Pending Approval"],
    ["approved", "Approved"],
    ["rejected_at_stage_2", "Rejected"],
    ["correction_required_at_stage_3", "Correction Required"],
    ["resubmitted_after_correction", "Pending Approval"],
    ["resubmitted_after_rejection", "Pending Approval"],
    ["cancelled", "Cancelled"],
  ] as const)("renders the %s status badge", async (name, label) => {
    mockOk(fixtures[name]);
    renderView();
    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it("uses the slate status token for the cancelled badge", async () => {
    mockOk(fixtures.cancelled);
    renderView();
    const badge = await screen.findByText("Cancelled");
    expect(badge.className).toContain("status-cancelled");
  });

  it("composes the pending current-status card from response fields", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();
    const card = within(await screen.findByLabelText("Current status"));
    expect(
      card.getByText(textContent("Awaiting Supervisor review"))
    ).toBeInTheDocument();
    expect(card.getByText("with Mr. Chikondi Banda")).toBeInTheDocument();
    expect(card.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(card.getByText(/Assigned/)).toBeInTheDocument();
  });

  it("composes the approved current-status card with the approval time", async () => {
    mockOk(fixtures.approved);
    renderView("app-approved");
    const card = within(await screen.findByLabelText("Current status"));
    expect(
      card.getByText("Fully approved on 18 Oct 2026, 08:20")
    ).toBeInTheDocument();
  });

  it("renders stages in order and de-emphasizes upcoming ones", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();
    const stepper = within(await screen.findByLabelText("Approval progress"));

    expect(stepper.getAllByRole("listitem")).toHaveLength(4);
    expect(stepper.getByText("Supervisor")).toBeInTheDocument();
    expect(stepper.getByText("HOD")).toBeInTheDocument();
    expect(stepper.getByText("Registrar")).toBeInTheDocument();
    expect(stepper.getByText("DVC")).toBeInTheDocument();
    // The three not-yet-reached stages stay quiet and unlabelled.
    expect(document.querySelectorAll('[data-state="pending"]')).toHaveLength(3);
    expect(stepper.getByText(/Assigned/)).toBeInTheDocument();
    expect(stepCount()).toBe(1);
  });

  it("shows a skipped stage with the reason, and keeps it in the chain", async () => {
    mockOk(fixtures.pending_with_skipped_stage);
    renderView();
    const stepper = within(await screen.findByLabelText("Approval progress"));

    // The applicant held the HOD stage, so it was skipped and the chain opened
    // at the Registrar. The stage stays listed, not dropped: a reader has to be
    // able to tell a deliberate skip from a stage that was quietly removed.
    expect(stepper.getAllByRole("listitem")).toHaveLength(4);
    expect(document.querySelector('[data-state="skipped"]')).toBeInTheDocument();
    expect(
      stepper.getByText(/Applicant cannot approve their own application/)
    ).toBeInTheDocument();
    expect(stepper.getByText(/Assigned/)).toBeInTheDocument();
    expect(document.querySelectorAll('[data-state="pending"]')).toHaveLength(1);
    expect(stepCount()).toBe(1);
  });

  it("shows a colleague deciding the section the applicant shared, with nothing skipped", async () => {
    mockOk(fixtures.pending_with_applicant_excluded);
    renderView();
    const stepper = within(await screen.findByLabelText("Approval progress"));

    expect(stepper.getAllByRole("listitem")).toHaveLength(4);
    // The applicant is removed from the section's eligibility at submission, so
    // the chain runs through their section with a colleague instead of skipping it.
    expect(document.querySelector('[data-state="skipped"]')).not.toBeInTheDocument();
    expect(stepper.getByText("Ms. Grace Kanyama")).toBeInTheDocument();
    expect(stepper.getByText(/Assigned/)).toBeInTheDocument();
    expect(document.querySelectorAll('[data-state="pending"]')).toHaveLength(1);
    expect(stepCount()).toBe(1);
  });

  it("marks exactly one aria-current=step for pending and none otherwise", async () => {
    mockOk(fixtures.pending_mid_workflow);
    const pending = renderView();
    await screen.findByText("Pending Approval");
    expect(stepCount()).toBe(1);
    pending.unmount();

    mockOk(fixtures.approved);
    const approvedRender = renderView("app-approved");
    await screen.findByText("Approved");
    expect(stepCount()).toBe(0);
    approvedRender.unmount();

    mockOk(fixtures.rejected_at_stage_2);
    renderView("app-rejected");
    await screen.findByText("Rejected");
    expect(stepCount()).toBe(0);
  });

  it("shows the delegate acting-for chip and the reassignment event", async () => {
    mockOk(fixtures.pending_with_delegate);
    renderView();
    await screen.findByText("Pending Approval");
    expect(screen.getByText(/Acting for Dr. Grace Mwale/)).toBeInTheDocument();
    expect(screen.getByText("Application reassigned")).toBeInTheDocument();
  });
});

describe("TrackingView · rejected", () => {
  it("shows the reason block, Workflow stopped, the panel and the resubmit link", async () => {
    mockOk(fixtures.rejected_at_stage_2);
    renderView();
    await screen.findByText("Rejected");

    expect(screen.getByText("Workflow stopped.")).toBeInTheDocument();

    const panel = within(await screen.findByLabelText("Rejection details"));
    expect(panel.getByText("Reason")).toBeInTheDocument();
    expect(screen.getAllByText(/Peak teaching period/).length).toBeGreaterThan(0);
    expect(panel.getByText("Stage 2 · Dean")).toBeInTheDocument();
    expect(panel.getByText("Dr. Anne Banda")).toBeInTheDocument();
    expect(panel.getByText("16 Oct 2026, 13:40")).toBeInTheDocument();
    expect(
      screen.getByText(
        textContent(
          "When you resubmit, this application returns to Dean."
        )
      )
    ).toBeInTheDocument();

    const link = screen.getByRole("link", { name: "Edit & resubmit" });
    expect(link).toHaveAttribute("href", "/applications/app-rejected/edit");
  });

  it("hides the resubmit button when can_resubmit is false", async () => {
    const data = clone(fixtures.rejected_at_stage_2);
    data.resubmission.can_resubmit = false;
    mockOk(data);
    renderView();
    await screen.findByText("Rejected");
    expect(
      screen.queryByRole("link", { name: "Edit & resubmit" })
    ).not.toBeInTheDocument();
  });
});

describe("TrackingView · correction", () => {
  it("shows the correction panel and resubmit link", async () => {
    mockOk(fixtures.correction_required_at_stage_3);
    renderView();
    await screen.findByText("Correction Required");

    const panel = within(await screen.findByLabelText("Correction details"));
    expect(panel.getByText("Comment")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Supporting documents must be uploaded/).length
    ).toBeGreaterThan(0);
    expect(panel.getByText("Stage 3 · Registrar")).toBeInTheDocument();
    expect(panel.getByText("Dr. Joyce Phiri")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Edit & resubmit" });
    expect(link).toHaveAttribute("href", "/applications/app-correction/edit");
  });
});

describe("TrackingView · resubmission", () => {
  it("shows the resubmission note and keeps the reference number", async () => {
    mockOk(fixtures.resubmitted_after_correction);
    renderView();
    await screen.findByText("Pending Approval");

    expect(screen.getByText("LV-2026-27-900007")).toBeInTheDocument();
    expect(
      screen.getByText(
        textContent("Resubmitted 1 time · last on 19 Oct 2026, 11:00")
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Rejection details")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Correction details")
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Workflow stopped.")).not.toBeInTheDocument();
  });

  it("shows the note and awaiting rejecting stage after rejection resubmission", async () => {
    mockOk(fixtures.resubmitted_after_rejection);
    renderView();
    await screen.findByText("Pending Approval");
    expect(
      screen.getByText(
        textContent("Resubmitted 1 time · last on 20 Oct 2026, 15:12")
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(textContent("Awaiting Dean review"))
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Edit & resubmit" })
    ).not.toBeInTheDocument();
  });
});

describe("TrackingView · activity timeline", () => {
  it("renders event titles with actors and comments", async () => {
    mockOk(fixtures.pending_mid_workflow);
    renderView();
    await screen.findByText("Pending Approval");

    expect(screen.getByText("Application submitted")).toBeInTheDocument();
    expect(screen.getByText("Supervisor approved")).toBeInTheDocument();
    expect(screen.getByText("Mr. Chikondi Banda · Supervisor")).toBeInTheDocument();
    expect(screen.getAllByText("Verified. Forwarded.").length).toBeGreaterThan(0);
  });

  it("renders the resubmitted event with its number", async () => {
    mockOk(fixtures.resubmitted_after_correction);
    renderView();
    await screen.findByText("Pending Approval");
    expect(screen.getByText("You resubmitted (#1)")).toBeInTheDocument();
  });

  it("falls back to 'Workflow update' for unknown event types", async () => {
    const data = clone(fixtures.approved);
    data.events[0].type = "delegated_to_someone_else";
    mockOk(data);
    renderView();
    expect(await screen.findByText("Workflow update")).toBeInTheDocument();
  });

  it("renders <time> with the formatted local time in the activity list", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();
    await screen.findByText("Pending Approval");

    const activity = screen.getByLabelText("Activity history");
    const times = within(activity).getAllByRole("time");
    expect(times.length).toBeGreaterThan(0);
    expect(times[0].textContent).toBe("12 Oct 2026, 09:15");
    expect(times[0].getAttribute("dateTime")).toBe("2026-10-12T07:15:03Z");
  });
});

describe("TrackingView · supporting documents", () => {
  beforeEach(() => {
    vi.mocked(listDocuments).mockReset();
    vi.mocked(listDocuments).mockResolvedValue([]);
  });

  it("renders active documents with an Open button", async () => {
    mockOk(fixtures.resubmitted_after_correction);
    renderView();

    const card = within(await screen.findByLabelText("Supporting documents"));
    expect(card.getByText("medical-certificate-v2.pdf")).toBeInTheDocument();
    expect(card.getByRole("button", { name: "Open" })).toBeInTheDocument();
  });

  it("shows the empty state when no documents are attached", async () => {
    mockOk(fixtures.pending_first_stage);
    renderView();

    const card = within(await screen.findByLabelText("Supporting documents"));
    expect(
      card.getByText("No supporting documents attached")
    ).toBeInTheDocument();
  });

  it("renders replaced and removed rows in the collapsed archive section", async () => {
    mockOk(fixtures.correction_required_at_stage_3);
    vi.mocked(listDocuments).mockResolvedValue([
      {
        id: "doc-old-replaced",
        file_url: "https://signed/old.pdf",
        file_name: "medical-certificate-v1.pdf",
        file_size: 1024,
        content_type: "application/pdf",
        uploaded_at: "2026-10-10T08:00:00Z",
        status: "retired",
        retired_at: "2026-10-18T08:45:00Z",
        retire_reason: "replaced",
        retired_by: { id: 8, name: "Test Employee" },
        replaced_by: { id: "doc-correction-active", file_name: "medical-certificate-v2.pdf" },
      },
      {
        id: "doc-old-removed",
        file_url: "https://signed/removed.pdf",
        file_name: "draft-note.txt",
        file_size: 512,
        content_type: "text/plain",
        uploaded_at: "2026-10-01T08:00:00Z",
        status: "retired",
        retired_at: "2026-10-05T09:00:00Z",
        retire_reason: "removed",
        retired_by: { id: 8, name: "Test Employee" },
        replaced_by: null,
      },
    ]);
    renderView();
    const card = within(await screen.findByLabelText("Supporting documents"));

    const archive = await card.findByRole("button", {
      name: "Archived (2)",
    });
    expect(archive).toBeInTheDocument();
    archive.click();

    expect(await card.findByText("medical-certificate-v1.pdf")).toBeInTheDocument();
    expect(
      card.getByText("Replaced on 18 Oct 2026, 10:45")
    ).toBeInTheDocument();
    expect(card.getByText("draft-note.txt")).toBeInTheDocument();
    expect(card.getByText("Removed on 5 Oct 2026, 11:00")).toBeInTheDocument();

    const openButtons = card.getAllByRole("button", { name: "Open" });
    expect(openButtons).toHaveLength(2);
  });

  it("offers no Open button for removed (intentionally deleted) rows", async () => {
    mockOk(fixtures.correction_required_at_stage_3);
    vi.mocked(listDocuments).mockResolvedValue([
      {
        id: "doc-old-removed",
        file_url: "https://signed/removed.pdf",
        file_name: "draft-note.txt",
        file_size: 512,
        content_type: "text/plain",
        uploaded_at: "2026-10-01T08:00:00Z",
        status: "retired",
        retired_at: "2026-10-05T09:00:00Z",
        retire_reason: "removed",
        retired_by: { id: 8, name: "Test Employee" },
        replaced_by: null,
      },
    ]);
    renderView();
    const card = within(await screen.findByLabelText("Supporting documents"));
    const archive = await card.findByRole("button", { name: "Archived (1)" });
    archive.click();

    expect(await card.findByText("draft-note.txt")).toBeInTheDocument();
    expect(
      card.queryAllByRole("button", { name: "Open" }).length
    ).toBe(1); // only the active row
  });
});

describe("TrackingView · cancellation fields", () => {
  it("shows the open-cancellation pill when a request is awaiting approval", async () => {
    const data = clone(fixtures.approved);
    data.has_open_cancellation_request = true;
    mockOk(data);
    renderView("app-open-cancellation");

    await screen.findByText("Approved");
    expect(screen.getByText("Cancellation requested")).toBeInTheDocument();
  });

  it("shows the cancelled-on line when the leave was cancelled", async () => {
    const data = clone(fixtures.cancelled);
    data.cancelled_at = "2026-10-16T08:00:00Z";
    mockOk(data);
    renderView("app-cancelled-2");

    await screen.findByText("Cancelled");
    expect(screen.getByText(textContent("Cancelled on 16 Oct 2026, 10:00"))).toBeInTheDocument();
  });
});

describe("TrackingView · page states", () => {
  it("shows the loading skeleton while the request is in flight", () => {
    vi.mocked(fetchTracking).mockReturnValue(
      new Promise(() => {
        /* never resolves */
      })
    );
    renderView();
    expect(
      screen.getByLabelText("Loading application tracking")
    ).toBeInTheDocument();
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it("renders the 404 state with a back link", async () => {
    vi.mocked(fetchTracking).mockResolvedValue({
      ok: false,
      kind: "not_found",
    });
    renderView();
    expect(await screen.findByText("Application not found")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "My applications" })
    ).toBeInTheDocument();
  });

  it("renders the draft (409) state with a link to the draft editor", async () => {
    vi.mocked(fetchTracking).mockResolvedValue({
      ok: false,
      kind: "not_submitted",
    });
    renderView("app-draft-id");
    expect(
      await screen.findByText("This application is still a draft")
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Open draft" });
    expect(link).toHaveAttribute("href", "/dashboard/leave/app-draft-id/edit");
  });

  it("renders the network-error state and retries", async () => {
    vi.mocked(fetchTracking).mockResolvedValueOnce({
      ok: false,
      kind: "error",
      message: "Could not reach the server.",
    });
    mockOk(fixtures.pending_first_stage);

    renderView();
    expect(
      await screen.findByText("Could not load tracking information")
    ).toBeInTheDocument();
    expect(screen.getByText("Could not reach the server.")).toBeInTheDocument();

    screen.getByRole("button", { name: "Try again" }).click();
    expect(await screen.findByText("Pending Approval")).toBeInTheDocument();
  });
});