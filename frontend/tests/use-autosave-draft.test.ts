import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAutosaveDraft } from "@/lib/hooks/useAutosaveDraft";
import { updateLeaveApplication } from "@/lib/leave-api";

vi.mock("@/lib/leave-api", () => ({
  updateLeaveApplication: vi.fn(),
}));

const mockedUpdate = vi.mocked(updateLeaveApplication);

async function flushTimers(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
  });
}

describe("useAutosaveDraft", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedUpdate.mockReset();
    mockedUpdate.mockResolvedValue({} as never);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("persists the first field values changed after a draft is created live", async () => {
    const { rerender } = renderHook(
      ({ applicationId, data }) => useAutosaveDraft(applicationId, data),
      { initialProps: { applicationId: null as string | null, data: { reason: "" } } }
    );

    rerender({ applicationId: "draft-1", data: { reason: "Family visit" } });

    await flushTimers(800);

    expect(mockedUpdate).toHaveBeenCalledTimes(1);
    expect(mockedUpdate).toHaveBeenCalledWith("draft-1", { reason: "Family visit" });
  });

  it("does not save the server-loaded snapshot in edit mode until data changes", async () => {
    const { rerender } = renderHook(
      ({ applicationId, data }) => useAutosaveDraft(applicationId, data),
      {
        initialProps: {
          applicationId: "draft-1",
          data: { reason: "Loaded from server" },
        },
      }
    );

    await flushTimers(800);
    expect(mockedUpdate).not.toHaveBeenCalled();

    rerender({
      applicationId: "draft-1",
      data: { reason: "Loaded from server" },
    });

    await flushTimers(800);
    expect(mockedUpdate).not.toHaveBeenCalled();

    rerender({
      applicationId: "draft-1",
      data: { reason: "Edited after load" },
    });

    await flushTimers(800);
    expect(mockedUpdate).toHaveBeenCalledTimes(1);
    expect(mockedUpdate).toHaveBeenCalledWith("draft-1", {
      reason: "Edited after load",
    });
  });

  it("debounces rapid changes into a single save", async () => {
    const { rerender } = renderHook(
      ({ applicationId, data }) => useAutosaveDraft(applicationId, data),
      { initialProps: { applicationId: null as string | null, data: { reason: "" } } }
    );

    rerender({ applicationId: "draft-1", data: { reason: "a" } });
    await flushTimers(400);
    rerender({ applicationId: "draft-1", data: { reason: "ab" } });
    await flushTimers(400);
    rerender({ applicationId: "draft-1", data: { reason: "abc" } });
    await flushTimers(800);

    expect(mockedUpdate).toHaveBeenCalledTimes(1);
    expect(mockedUpdate).toHaveBeenCalledWith("draft-1", { reason: "abc" });
  });

  it("reports an error status when the save fails", async () => {
    mockedUpdate.mockRejectedValueOnce(new Error("boom"));

    const { rerender, result } = renderHook(
      ({ applicationId, data }) => useAutosaveDraft(applicationId, data),
      { initialProps: { applicationId: null as string | null, data: { reason: "" } } }
    );

    rerender({ applicationId: "draft-1", data: { reason: "Family visit" } });
    await flushTimers(800);

    expect(result.current.saveStatus).toBe("error");
  });
});