import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";

function submittedApplication(id: string) {
  return {
    id,
    leave_type_id: 1,
    start_date: "2026-10-01",
    end_date: "2026-10-05",
    calculated_days: 3,
    reason: "Family visit",
    status: "submitted",
    reference_number: "LUANAR-2026-0001",
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    submitted_at: "2026-09-20T11:00:00Z",
    documents: [],
  };
}

describe("LeaveApplicationForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a read-only notice when editing a submitted application", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(submittedApplication("app-1")), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    expect(
      await screen.findByText(/application already submitted/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/can no longer be edited/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /review application/i })
    ).not.toBeInTheDocument();
  });

  it("surfaces a load error when the application cannot be fetched", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 404 }));

    render(<LeaveApplicationForm mode="edit" applicationId="app-1" />);

    expect(
      await screen.findByRole("alert") 
   ).toHaveTextContent(/could not load this draft/i);
  });
});