// @vitest-environment node
import { describe, expect, it } from "vitest";

import {
  decisionLabel,
  decisionPastTense,
  formatBytes,
  formatDateRange,
  leaveHistoryNote,
} from "@/lib/approvals/format";

describe("approvals format helpers", () => {
  it("renders date ranges", () => {
    expect(formatDateRange("2026-11-02", "2026-11-06")).toBe(
      "2 Nov 2026 – 6 Nov 2026"
    );
    expect(formatDateRange("2026-11-02", null)).toBe("2 Nov 2026");
    expect(formatDateRange(null, null)).toBe("");
  });

  it("formats byte sizes", () => {
    expect(formatBytes(0)).toBe("");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
    expect(formatBytes(512)).toBe("512 B");
  });

  it("maps decision actions to display labels", () => {
    expect(decisionLabel("approve")).toBe("Approve");
    expect(decisionLabel("reject")).toBe("Reject");
    expect(decisionLabel("return_for_correction")).toBe("Return for Correction");
    expect(decisionPastTense("approve")).toBe("approved");
    expect(decisionPastTense("return_for_correction")).toBe(
      "returned for correction"
    );
  });

  it("produces leave history notes", () => {
    expect(
      leaveHistoryNote({ available: false, scope: null, items: [] })
    ).toBe("Leave history is not available for your role.");
    expect(
      leaveHistoryNote({
        available: true,
        scope: "current_financial_year",
        items: [],
      })
    ).toBe("Showing leave within the current financial year.");
    expect(
      leaveHistoryNote({ available: true, scope: null, items: [] })
    ).toBe("Showing the employee's recent leave history.");
  });
});