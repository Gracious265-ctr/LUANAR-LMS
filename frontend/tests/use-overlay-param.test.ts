import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useOverlayParam } from "@/lib/hooks/useOverlayParam";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/hr-admin/calendar" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

const REAL_HISTORY_LENGTH = window.history.length;

/**
 * JSDOM's history length only ever grows within a file and `replaceState`
 * cannot truncate it, so a test that pushed an entry would otherwise force
 * every later test down the `router.back()` branch. Overriding the property
 * makes each branch reachable on its own terms.
 */
function setHistoryLength(length: number) {
  Object.defineProperty(window.history, "length", {
    value: length,
    configurable: true,
  });
}

describe("useOverlayParam", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathnameRef.current = "/hr-admin/calendar";
    searchParamsRef.current = new URLSearchParams();
    // A lone entry: the direct-visit case, with nowhere to step back to.
    setHistoryLength(1);
  });

  afterEach(() => {
    setHistoryLength(REAL_HISTORY_LENGTH);
  });

  it("is closed when the key is absent", () => {
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.isOpen).toBe(false);
    expect(result.current.target).toBeNull();
    expect(result.current.isCreate).toBe(false);
  });

  it('reads "new" as a create target rather than a row id', () => {
    searchParamsRef.current = new URLSearchParams("holiday=new");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.isOpen).toBe(true);
    expect(result.current.isCreate).toBe(true);
  });

  it("reads any other value as the row id", () => {
    searchParamsRef.current = new URLSearchParams("holiday=42");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.target).toBe("42");
    expect(result.current.isCreate).toBe(false);
  });

  it("only reacts to its own key, so a page can host two overlays", () => {
    searchParamsRef.current = new URLSearchParams("financialYear=7");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.isOpen).toBe(false);
  });

  it("pushes the create target without disturbing the host's own query", () => {
    searchParamsRef.current = new URLSearchParams("year=2026");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    act(() => result.current.openCreate());

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/calendar?year=2026&holiday=new"
    );
  });

  it("pushes a row id as the target", () => {
    const { result } = renderHook(() => useOverlayParam("leaveType"));

    act(() => result.current.openEdit(9));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/calendar?leaveType=9"
    );
  });

  it("replaces the host's copy of the key rather than duplicating it", () => {
    searchParamsRef.current = new URLSearchParams("holiday=3");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    act(() => result.current.openEdit(4));

    const url = routerMock.push.mock.calls[0][0] as string;
    expect(url.match(/holiday=/g)).toHaveLength(1);
    expect(url).toContain("holiday=4");
  });

  it("steps back through history on close when there is somewhere to go", () => {
    setHistoryLength(2);
    const { result } = renderHook(() => useOverlayParam("holiday"));

    act(() => result.current.close());

    expect(routerMock.back).toHaveBeenCalled();
    expect(routerMock.replace).not.toHaveBeenCalled();
  });

  it("falls back to a replace on a direct visit to the deep link", () => {
    searchParamsRef.current = new URLSearchParams("holiday=new");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    act(() => result.current.close());

    expect(routerMock.back).not.toHaveBeenCalled();
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/hr-admin/calendar"
    );
  });

  it("keeps other keys when falling back to a replace", () => {
    searchParamsRef.current = new URLSearchParams("year=2026&holiday=5");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    act(() => result.current.close());

    expect(routerMock.replace).toHaveBeenCalledWith(
      "/hr-admin/calendar?year=2026"
    );
  });

  it("exposes a full href without its key for a clear-filters escape hatch", () => {
    searchParamsRef.current = new URLSearchParams("year=2026&holiday=5");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.hrefWithoutParam).toBe(
      "/hr-admin/calendar?year=2026"
    );
  });

  it("drops the query entirely when the key was the only param", () => {
    searchParamsRef.current = new URLSearchParams("holiday=5");
    const { result } = renderHook(() => useOverlayParam("holiday"));

    expect(result.current.hrefWithoutParam).toBe(
      "/hr-admin/calendar"
    );
  });
});
