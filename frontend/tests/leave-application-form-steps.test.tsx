import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { pushToast } from "@/components/ui/toast";

vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));
vi.mock("@/lib/hooks/useLeaveValidation", () => ({
  useLeaveValidation: vi.fn(),
}));
vi.mock("@/components/ui/toast", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/components/ui/toast")>();
  return { ...actual, pushToast: vi.fn() };
});

const VALID_RESULT = {
  valid: true,
  working_days: 3,
  calendar_days: 5,
  financial_year: "2026-27",
  available_balance: "24",
  balance_after_if_approved: "21",
  entitlement_balance: "24",
  errors: [],
  warnings: [],
  skipped_checks: [],
};

function draft(overrides: Record<string, unknown> = {}) {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-10-01",
    end_date: "2026-10-05",
    calculated_days: 3,
    reason: "Family visit",
    status: "draft",
    reference_number: null,
    documents: [],
    ...overrides,
  };
}

function states(): (string | null)[] {
  return Array.from(document.querySelectorAll("li[data-state]")).map((li) =>
    li.getAttribute("data-state")
  );
}

function mockFetch(app: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/leave/leave-applications/")) {
        return new Response(JSON.stringify(app), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(null, { status: 404 });
    })
  );
}

describe("LeaveApplicationForm multi-step flow", () => {
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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts on step one with four steps, the documents step skipped", async () => {
    mockFetch(draft());

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    expect(states()).toEqual(["current", "pending", "skipped", "pending"]);
  });

  it("walks forward with Next and lifts the documents step into view", async () => {
    // The type does not need documents but one is already attached, so step 3
    // is present rather than skipped.
    mockFetch(
      draft({
        documents: [
          {
            id: "doc-1",
            file_url: "https://signed/doc-1.pdf",
            file_name: "letter.pdf",
            file_size: 2048,
            content_type: "application/pdf",
            uploaded_at: "2026-09-20T10:00:00Z",
            status: "active",
            retired_at: null,
            retire_reason: null,
            retired_by: null,
            replaced_by: null,
          },
        ],
      })
    );

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(states()).toEqual(["completed", "current", "pending", "pending"]);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(states()).toEqual(["completed", "completed", "current", "pending"]);
    expect(await screen.findByText(/drag & drop files/i)).toBeInTheDocument();
  });

  it("jumps back to an earlier step by clicking it", async () => {
    mockFetch(
      draft({
        documents: [
          {
            id: "doc-1",
            file_url: "https://signed/doc-1.pdf",
            file_name: "letter.pdf",
            file_size: 2048,
            content_type: "application/pdf",
            uploaded_at: "2026-09-20T10:00:00Z",
            status: "active",
            retired_at: null,
            retire_reason: null,
            retired_by: null,
            replaced_by: null,
          },
        ],
      })
    );

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    fireEvent.click(
      screen.getByRole("button", { name: "Go to Dates & leave type" })
    );

    expect(states()).toEqual(["current", "pending", "pending", "pending"]);
  });

  it("will not advance a step while it holds an error", async () => {
    mockFetch(draft());
    vi.mocked(useLeaveValidation).mockReturnValue({
      result: {
        ...VALID_RESULT,
        valid: false,
        errors: [
          { code: "START_IN_PAST", field: "start_date", message: "The start date is in the past." },
        ],
      } as never,
      isLoading: false,
      error: null,
    });

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
    );
  });

  it("blocks the documents step until a document is attached", async () => {
    vi.mocked(getLeaveTypes).mockResolvedValue([
      { id: 1, name: "Maternity Leave", requiresDocuments: true, maxDurationDays: 90 },
    ]);
    mockFetch(draft());

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(states()).toEqual(["completed", "completed", "current", "pending"]);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("skips straight from reason to review when no documents are needed", async () => {
    mockFetch(draft());

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(states()).toEqual(["completed", "completed", "skipped", "current"]);
    expect(
      screen.getByRole("button", { name: "Review Application" })
    ).toBeInTheDocument();
  });

  it("warm-starts a new application from the saved defaults", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("form-defaults")) {
          return new Response(
            JSON.stringify({
              last_leave_type_id: 1,
              default_start_date: "2026-10-13",
              balance_by_type: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(null, { status: 404 });
      })
    );

    render(<LeaveApplicationForm mode="create" />);

    expect(await screen.findByText("Annual Leave")).toBeInTheDocument();
    expect(await screen.findByText(/13 Oct 2026/)).toBeInTheDocument();
  });

  it("raises a toast when an autosave fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          return new Response(null, { status: 500 });
        }
        return new Response(JSON.stringify(draft()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      })
    );

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    await screen.findByLabelText("Leave Type");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const reason = await screen.findByPlaceholderText(/provide a reason/i);
    fireEvent.change(reason, { target: { value: "A changed reason" } });

    await waitFor(() => expect(pushToast).toHaveBeenCalled(), { timeout: 3000 });
  });
});
