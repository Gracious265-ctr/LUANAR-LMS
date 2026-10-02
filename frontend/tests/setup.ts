import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  // No query by default, so an overlay driven by search params renders closed.
  // Tests that need one open override this with their own `useSearchParams`.
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

let narrow = false;
const listeners = new Set<(event: { matches: boolean }) => void>();

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: Object.assign(
    (query: string) => ({
      get matches() {
        // Only the dashboard's own query reports a narrow viewport; everything
        // else (prefers-reduced-motion, hover) stays false so the default
        // desktop baseline other tests are written against is preserved.
        return query.includes("max-width") ? narrow : false;
      },
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (
        _: string,
        listener: (event: { matches: boolean }) => void,
      ) => {
        listeners.add(listener);
      },
      removeEventListener: (
        _: string,
        listener: (event: { matches: boolean }) => void,
      ) => {
        listeners.delete(listener);
      },
      dispatchEvent: () => false,
    }),
    {
      /** Lets a test simulate resizing across the mobile breakpoint. */
      setNarrow: (value: boolean) => {
        narrow = value;
        listeners.forEach((listener) => listener({ matches: value }));
      },
    },
  ),
});

/* Radix primitives drive their open/close and positioning logic from pointer
   capture, layout measurement and the Web Animations API. jsdom implements
   none of these, so without the shims below a Radix `Select` throws on
   `pointerdown` and never opens, and `Dialog` cannot complete its enter
   transition. The values are deliberately inert: tests assert on DOM, not on
   geometry. */

if (!("PointerEvent" in window)) {
  class PointerEvent extends MouseEvent {
    readonly pointerId: number;
    readonly pointerType: string;
    readonly isPrimary: boolean;

    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params);
      this.pointerId = params.pointerId ?? 1;
      this.pointerType = params.pointerType ?? "mouse";
      this.isPrimary = params.isPrimary ?? true;
    }
  }
  Object.defineProperty(window, "PointerEvent", { writable: true, value: PointerEvent });
  Object.defineProperty(globalThis, "PointerEvent", { writable: true, value: PointerEvent });
}

Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.setPointerCapture ??= () => {};
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.scrollIntoView ??= () => {};
Element.prototype.getAnimations ??= () => [];

if (!("ResizeObserver" in window)) {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Object.defineProperty(window, "ResizeObserver", { writable: true, value: ResizeObserver });
  Object.defineProperty(globalThis, "ResizeObserver", { writable: true, value: ResizeObserver });
}
