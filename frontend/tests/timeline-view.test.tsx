import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TimelineView } from "@/components/leave/timeline-view";
import type { TimelineEntry } from "@/lib/leave-history";

const baseEntry: TimelineEntry = {
  id: 1,
  kind: "submission",
  action: "leave_application.submitted",
  action_label: "Submitted for approval",
  occurred_at: "2026-09-26T08:00:00Z",
  actor: { id: 11, name: "Jane Doe" },
  target_type: "leaveapplication",
  state_transition: { from: "draft", to: "submitted" },
  summary: "",
  metadata: {},
  stage_order: null,
  resubmission_number: null,
};

function makeEntry(overrides: Partial<TimelineEntry>): TimelineEntry {
  return { ...baseEntry, ...overrides, id: Math.random() };
}

describe("TimelineView", () => {
  it("shows the empty message when there are no entries", () => {
    render(<TimelineView entries={[]} />);
    expect(
      screen.getByText("No recorded events for this application.")
    ).toBeInTheDocument();
  });

  it("renders the entry action label, actor and formatted time", () => {
    const entry = makeEntry({
      action_label: "Approved by Beatrice Chanda",
      occurred_at: "2026-09-26T08:00:00Z",
    });
    render(<TimelineView entries={[entry]} />);

    expect(screen.getByText("Approved by Beatrice Chanda")).toBeInTheDocument();
    expect(screen.getByText("26 Sept 2026, 10:00")).toBeInTheDocument();
  });

  it("renders the summary and the stage/resubmission chips", () => {
    const entry = makeEntry({
      kind: "decision",
      action_label: "Approved",
      summary: "LV-2026-27-900001",
      stage_order: 2,
      resubmission_number: 1,
    });
    render(<TimelineView entries={[entry]} />);

    expect(screen.getByText("LV-2026-27-900001")).toBeInTheDocument();
    expect(screen.getByText("Stage 2")).toBeInTheDocument();
    expect(screen.getByText("Resubmission 1")).toBeInTheDocument();
  });

  it("renders entries in the order given (oldest first)", () => {
    const older = makeEntry({ action_label: "First", occurred_at: "2026-09-26T08:00:00Z" });
    const newer = makeEntry({ action_label: "Second", occurred_at: "2026-09-26T09:00:00Z" });
    render(<TimelineView entries={[older, newer]} />);

    const items = screen.getAllByText(/Earlier|First|Second|^/);
    const labels = items.map((node) => node.textContent);
    const firstIndex = labels.findIndex((label) => label === "First");
    const secondIndex = labels.findIndex((label) => label === "Second");
    expect(firstIndex).toBeGreaterThan(-1);
    expect(secondIndex).toBeGreaterThan(firstIndex);
  });

  it("exposes the entry kind as a glyph tooltip", () => {
    const entry = makeEntry({ kind: "cancellation", action_label: "Withdrawn" });
    render(<TimelineView entries={[entry]} />);
    expect(screen.getByTitle("Cancellation")).toBeInTheDocument();
  });
});