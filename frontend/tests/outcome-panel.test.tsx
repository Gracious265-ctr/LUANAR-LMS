import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OutcomePanel } from "@/components/tracking/OutcomePanel";
import { acceptRejection } from "@/lib/tracking/service";
import type { TrackingResponse } from "@/lib/tracking/types";

import rejected from "@/lib/tracking/__fixtures__/rejected_at_stage_2.json";

vi.mock("@/lib/tracking/service", () => ({
  acceptRejection: vi.fn(),
}));

function fixture(overrides: { accepted?: boolean } = {}): TrackingResponse {
  const data = JSON.parse(JSON.stringify(rejected)) as unknown as TrackingResponse;
  if (overrides.accepted) {
    data.rejection = {
      ...data.rejection!,
      accepted_at: "2026-10-17T08:00:00Z",
    };
    data.resubmission = {
      ...data.resubmission,
      can_resubmit: false,
      returns_to_stage: null,
    };
  }
  return data;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OutcomePanel", () => {
  it("offers both exits from an open rejection", () => {
    render(<OutcomePanel data={fixture()} />);

    expect(
      screen.getByRole("link", { name: /Edit & resubmit/i })
    ).toHaveAttribute("href", "/dashboard/leave/app-rejected/edit");
    expect(
      screen.getByRole("button", { name: /^Accept rejection$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/this application returns to/i)
    ).toBeInTheDocument();
  });

  it("accepts through a confirmation dialog and reports the reload", async () => {
    vi.mocked(acceptRejection).mockResolvedValue({ ok: true });
    const onAccepted = vi.fn();
    render(<OutcomePanel data={fixture()} onAccepted={onAccepted} />);

    fireEvent.click(
      screen.getByRole("button", { name: /^Accept rejection$/i })
    );

    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/Accept this rejection\?/i)).toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole("button", { name: /^Accept rejection$/i })
    );

    await waitFor(() =>
      expect(acceptRejection).toHaveBeenCalledWith("app-rejected")
    );
    expect(onAccepted).toHaveBeenCalled();
  });

  it("shows the acceptance time and hides every action once accepted", () => {
    render(<OutcomePanel data={fixture({ accepted: true })} />);

    expect(screen.getByText(/Rejection accepted on/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Edit & resubmit/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Accept rejection$/i })
    ).not.toBeInTheDocument();
  });

  it("keeps the dialog open and shows the error when acceptance fails", async () => {
    vi.mocked(acceptRejection).mockResolvedValue({
      ok: false,
      message: "The rejection could not be accepted.",
    });
    const onAccepted = vi.fn();
    render(<OutcomePanel data={fixture()} onAccepted={onAccepted} />);

    fireEvent.click(
      screen.getByRole("button", { name: /^Accept rejection$/i })
    );
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(
      within(dialog).getByRole("button", { name: /^Accept rejection$/i })
    );

    expect(
      await screen.findByText("The rejection could not be accepted.")
    ).toBeInTheDocument();
    expect(onAccepted).not.toHaveBeenCalled();
  });
});
