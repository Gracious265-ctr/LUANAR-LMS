import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { validateLeave } from "@/lib/leave-validation";

vi.mock("@/lib/leave-validation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-validation")>();
  return { ...actual, validateLeave: vi.fn() };
});

const mockValidate = vi.mocked(validateLeave);

const validResult = {
  valid: true,
  working_days: 5,
  calendar_days: 5,
  financial_year: "2026-27",
  available_balance: "24",
  balance_after_if_approved: "19",
  errors: [],
  warnings: [],
  skipped_checks: ["documents", "reason"],
};

const input = {
  leave_type_id: 1,
  start_date: "2026-09-28",
  end_date: "2026-10-02",
  draft_id: "draft-1",
};

describe("useLeaveValidation", () => {
  beforeEach(() => {
    mockValidate.mockReset();
    mockValidate.mockResolvedValue(validResult);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces and fires a single request after 400ms", async () => {
    const { result } = renderHook(() => useLeaveValidation(input));

    expect(mockValidate).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(399);
    });
    expect(mockValidate).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(mockValidate).toHaveBeenCalledTimes(1);
    expect(mockValidate).toHaveBeenCalledWith(
      {
        leave_type_id: 1,
        start_date: "2026-09-28",
        end_date: "2026-10-02",
        draft_id: "draft-1",
        application_id: null,
      },
      expect.any(AbortSignal)
    );

    expect(result.current.result?.valid).toBe(true);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("cancels a pending (stale) request when inputs change before the debounce", async () => {
    const { rerender } = renderHook(({ value }) => useLeaveValidation(value), {
      initialProps: { value: input },
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    rerender({ value: { ...input, end_date: "2026-10-05" } });

    await act(async () => {
      vi.advanceTimersByTime(400);
    });

    expect(mockValidate).toHaveBeenCalledTimes(1);
    expect(mockValidate).toHaveBeenCalledWith(
      expect.objectContaining({ end_date: "2026-10-05" }),
      expect.any(AbortSignal)
    );
  });

  it("does not fire when the inputs are incomplete", async () => {
    renderHook(() =>
      useLeaveValidation({ leave_type_id: 1, start_date: "2026-09-28", end_date: null })
    );
    await act(async () => {
      vi.advanceTimersByTime(500);
    });
    expect(mockValidate).not.toHaveBeenCalled();
  });

  it("exposes a network error when the request fails", async () => {
    mockValidate.mockRejectedValueOnce(new Error("boom"));
    const { result } = renderHook(() => useLeaveValidation(input));

    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(result.current.error).not.toBeNull();
    expect(result.current.result).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });
});