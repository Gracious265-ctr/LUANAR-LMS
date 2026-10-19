import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/plans/service", () => ({
  getScopeOptions: vi.fn(),
  getTeamPlans: vi.fn(),
}));

import { useTeamPlans } from "@/lib/hooks/useTeamPlans";
import { getScopeOptions, getTeamPlans } from "@/lib/plans/service";
import { makeScope, makeTeamPlans } from "@/lib/plans/__fixtures__";

const mockScopes = vi.mocked(getScopeOptions);
const mockTeam = vi.mocked(getTeamPlans);

beforeEach(() => {
  mockScopes.mockReset();
  mockTeam.mockReset();
  mockTeam.mockResolvedValue(makeTeamPlans());
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useTeamPlans", () => {
  it("requests plans for the default scope once scopes resolve", async () => {
    mockScopes.mockResolvedValue([makeScope({ id: "team:7" })]);

    const { result } = renderHook(() => useTeamPlans());

    await waitFor(() => expect(mockTeam).toHaveBeenCalledTimes(1));
    expect(mockTeam).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "team:7" })
    );
    expect(result.current.error).toBeNull();
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it("does not request plans when the viewer has no scope", async () => {
    mockScopes.mockResolvedValue([]);

    const { result } = renderHook(() => useTeamPlans());

    await waitFor(() => expect(result.current.scopesLoaded).toBe(true));
    expect(mockTeam).not.toHaveBeenCalled();
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.scopes).toEqual([]);
  });

  it("does not request plans before the scope list has loaded", async () => {
    let resolveScopes: (value: ReturnType<typeof makeScope>[]) => void = () => {};
    mockScopes.mockReturnValue(
      new Promise((resolve) => {
        resolveScopes = resolve;
      })
    );

    const { result } = renderHook(() => useTeamPlans());

    expect(result.current.scopesLoaded).toBe(false);
    expect(mockTeam).not.toHaveBeenCalled();

    resolveScopes([makeScope({ id: "team:3" })]);
    await waitFor(() => expect(mockTeam).toHaveBeenCalledTimes(1));
  });

  it("surfaces a scope-loading failure without requesting plans", async () => {
    mockScopes.mockRejectedValue(new Error("scopes down"));

    const { result } = renderHook(() => useTeamPlans());

    await waitFor(() => expect(result.current.error).toBe("scopes down"));
    expect(mockTeam).not.toHaveBeenCalled();
  });
});
