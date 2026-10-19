import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveApplicationOverlay } from "@/components/leave/LeaveApplicationOverlay";
import type { LeaveApplication } from "@/lib/leave-api";
import { createLeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { submitApplication } from "@/lib/leave-validation";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";

const { replaceMock } = vi.hoisted(() => ({ replaceMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/leave/drafts",
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/leave-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-api")>();
  return {
    ...actual,
    getLeaveApplication: vi.fn(),
    createLeaveApplication: vi.fn(),
    updateLeaveApplication: vi.fn(),
  };
});

vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));

vi.mock("@/lib/leave-validation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-validation")>();
  return { ...actual, submitApplication: vi.fn() };
});

vi.mock("@/lib/hooks/useLeaveValidation", () => ({
  useLeaveValidation: vi.fn(),
}));

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

const VALID_RESULT = {
  valid: true,
  working_days: 3,
  calendar_days: 5,
  financial_year: "2026-27",
  available_balance: "24",
  balance_after_if_approved: "21",
  errors: [],
  warnings: [],
  skipped_checks: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getLeaveTypes).mockResolvedValue([
    { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: 30 },
  ]);
  vi.mocked(useLeaveValidation).mockReturnValue({
    result: VALID_RESULT as never,
    isLoading: false,
    error: null,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/leave/leave-applications/")) {
        return new Response(JSON.stringify(makeApplication()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/leave/leave-types/")) {
        return new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/leave/validate/")) {
        return new Response(JSON.stringify(VALID_RESULT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(null, { status: 404 });
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LeaveApplicationOverlay", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <LeaveApplicationOverlay open={false} mode="create" onOpenChange={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("opens on the form stage for a new application", () => {
    render(
      <LeaveApplicationOverlay open mode="create" onOpenChange={vi.fn()} />
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("New leave application")).toBeInTheDocument();
  });

  it("deep-links straight into the review stage", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());

    render(
      <LeaveApplicationOverlay
        open
        mode="edit"
        applicationId="app-1"
        initialStage="review"
        onOpenChange={vi.fn()}
      />
    );

    expect(
      await screen.findByRole("button", { name: "Submit application" })
    ).toBeInTheDocument();
    // The page-level back link belongs to the standalone page only.
    expect(screen.queryByText("Back to draft")).not.toBeInTheDocument();
  });

  it("deep-links to the confirmation stage", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(
      makeApplication({
        status: "submitted",
        reference_number: "LV-2026-27-000009",
        submitted_at: "2026-09-21T10:00:00Z",
      })
    );

    render(
      <LeaveApplicationOverlay
        open
        mode="edit"
        applicationId="app-1"
        initialStage="done"
        onOpenChange={vi.fn()}
      />
    );

    expect(await screen.findByText("LV-2026-27-000009")).toBeInTheDocument();
  });

  it("rewrites the URL to the created draft so a refresh resumes it", async () => {
    vi.mocked(createLeaveApplication).mockResolvedValue(
      makeApplication({ id: "draft-9" }) as never
    );

    render(
      <LeaveApplicationOverlay open mode="create" onOpenChange={vi.fn()} />
    );

    const reason = await screen.findByPlaceholderText(/provide a reason/i);
    fireEvent.change(reason, { target: { value: "Family visit" } });

    await waitFor(() =>
      expect(replaceMock).toHaveBeenCalledWith("/dashboard/leave/drafts?edit=draft-9")
    );
  });

  it("advances to review without navigating, then submits to confirmation", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());
    vi.mocked(createLeaveApplication).mockResolvedValue(
      makeApplication({ id: "draft-9" }) as never
    );
    vi.mocked(submitApplication).mockResolvedValue({
      id: "draft-9",
      reference_number: "LV-2026-27-000010",
      status: "submitted",
      submitted_at: "2026-09-21T10:00:00Z",
      working_days: 3,
      calendar_days: 5,
      leave_type: { id: 1 },
      start_date: "2026-10-01",
      end_date: "2026-10-05",
    } as never);
    vi.mocked(getLeaveApplication).mockResolvedValue(
      makeApplication({
        id: "draft-9",
        status: "submitted",
        reference_number: "LV-2026-27-000010",
        submitted_at: "2026-09-21T10:00:00Z",
      })
    );

    const onSubmitted = vi.fn();
    render(
      <LeaveApplicationOverlay
        open
        mode="create"
        onOpenChange={vi.fn()}
        onSubmitted={onSubmitted}
      />
    );

    const reason = await screen.findByPlaceholderText(/provide a reason/i);
    fireEvent.change(reason, { target: { value: "Family visit" } });

    const review = await screen.findByRole("button", {
      name: "Review Application",
    });
    await waitFor(() => expect(review).toBeEnabled());
    fireEvent.click(review);

    const submit = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(submit);

    expect(await screen.findByText("LV-2026-27-000010")).toBeInTheDocument();
    expect(onSubmitted).toHaveBeenCalledWith("draft-9");
  });

  it("steps back from review to the form without a navigation", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());

    render(
      <LeaveApplicationOverlay
        open
        mode="edit"
        applicationId="app-1"
        initialStage="review"
        onOpenChange={vi.fn()}
      />
    );

    const back = await screen.findByRole("button", { name: "Back to edit" });
    fireEvent.click(back);

    expect(await screen.findByText("New leave application")).toBeInTheDocument();
  });

  it("reports each stage transition so the host can mirror it into the URL", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(
      makeApplication({ id: "draft-9", status: "submitted", reference_number: "LV-1" })
    );
    vi.mocked(createLeaveApplication).mockResolvedValue(
      makeApplication({ id: "draft-9" }) as never
    );
    vi.mocked(submitApplication).mockResolvedValue({
      id: "draft-9",
      reference_number: "LV-1",
      status: "submitted",
      submitted_at: "2026-09-21T10:00:00Z",
      working_days: 3,
      calendar_days: 5,
      leave_type: { id: 1 },
      start_date: "2026-10-01",
      end_date: "2026-10-05",
    } as never);

    const onStageChange = vi.fn();
    render(
      <LeaveApplicationOverlay
        open
        mode="create"
        onOpenChange={vi.fn()}
        onStageChange={onStageChange}
      />
    );

    const reason = await screen.findByPlaceholderText(/provide a reason/i);
    fireEvent.change(reason, { target: { value: "Family visit" } });

    const review = await screen.findByRole("button", { name: "Review Application" });
    await waitFor(() => expect(review).toBeEnabled());
    fireEvent.click(review);

    // The draft id travels with the report: a create flow only learns it
    // partway through, and the URL has to name the draft from then on.
    await waitFor(() =>
      expect(onStageChange).toHaveBeenCalledWith("review", "draft-9")
    );

    const submit = await screen.findByRole("button", { name: "Submit application" });
    fireEvent.click(submit);

    await waitFor(() =>
      expect(onStageChange).toHaveBeenCalledWith("done", "draft-9")
    );
  });

  it("reports the step back from review to the form", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());
    const onStageChange = vi.fn();

    render(
      <LeaveApplicationOverlay
        open
        mode="edit"
        applicationId="app-1"
        initialStage="review"
        onOpenChange={vi.fn()}
        onStageChange={onStageChange}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Back to edit" }));

    await waitFor(() => expect(onStageChange).toHaveBeenCalledWith("form", "app-1"));
  });

  it("leaves the URL to the host: stage moves never navigate on their own", async () => {
    vi.mocked(getLeaveApplication).mockResolvedValue(makeApplication());

    render(
      <LeaveApplicationOverlay
        open
        mode="edit"
        applicationId="app-1"
        initialStage="review"
        onOpenChange={vi.fn()}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Back to edit" }));

    expect(await screen.findByText("New leave application")).toBeInTheDocument();
    // The draft-creation rewrite is the overlay's own; a stage change is not.
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("reports close to the host so it can clear the URL", async () => {
    const onOpenChange = vi.fn();
    render(
      <LeaveApplicationOverlay open mode="create" onOpenChange={onOpenChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("gives the leave type dropdown a stacking layer above the dialog", async () => {
    render(
      <LeaveApplicationOverlay open mode="create" onOpenChange={vi.fn()} />
    );

    // Guards the z-portal-above fix: SelectContent portals to <body> at
    // z-popover (100), which would render behind the dialog at z-modal (1010).
    // The trigger is disabled while the leave types load, so wait that out
    // before opening it.
    const trigger = screen.getByRole("combobox");
    await waitFor(() => expect(trigger).not.toBeDisabled());
    fireEvent.pointerDown(trigger);
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const content = document.querySelector("[data-slot='select-content']");
    expect(content?.className).toContain("z-portal-above");
  });
});
