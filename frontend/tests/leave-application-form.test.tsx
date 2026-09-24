import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";

function application(status: string, overrides: Record<string, unknown> = {}) {
  return {
    id: "app-1",
    leave_type_id: 1,
    start_date: "2026-10-01",
    end_date: "2026-10-05",
    calculated_days: 3,
    reason: "Family visit",
    status,
    reference_number: "LUANAR-2026-0001",
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    submitted_at: "2026-09-20T11:00:00Z",
    documents: [],
    ...overrides,
  };
}

const VALIDATION_RESULT = {
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

function mockApi(app: ReturnType<typeof application>) {
  vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/leave/leave-applications/app-1/")) {
      return new Response(JSON.stringify(app), {
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
      return new Response(JSON.stringify(VALIDATION_RESULT), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  });
}

describe("LeaveApplicationForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["submitted", "approved", "rejected", "cancelled"])(
    "shows a read-only notice when editing a %s application",
    async (statusName) => {
      mockApi(application(statusName));

      render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

      expect(
        await screen.findByText(/application no longer editable/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/read-only record/i)
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /review application/i })
      ).not.toBeInTheDocument();
      expect(screen.queryByText(/drag & drop files/i)).not.toBeInTheDocument();
    }
  );

  it("keeps the uploader editable and explains Replace on a correction edit", async () => {
    mockApi(
      application("correction_required", {
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

    expect(await screen.findByText(/drag & drop files/i)).toBeInTheDocument();
    expect(
      screen.getByText(/returned for correction/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/application no longer editable/i)
    ).not.toBeInTheDocument();
  });

  it("surfaces a load error when the application cannot be fetched", async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/leave/leave-types/")) {
        return new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(null, { status: 404 });
    });

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(/could not load this draft/i);
  });
});