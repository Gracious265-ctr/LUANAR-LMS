"use client";

import { useSyncExternalStore } from "react";

import { readThemeFromDocument, type Theme } from "@/lib/theme";

/**
 * Reports the theme currently on the document.
 *
 * The theme lives in the `<html>` class, so it is an external system rather than
 * React state — which is exactly what `useSyncExternalStore` is for. Deriving it
 * in an effect with `setState` would be the obvious alternative, but that
 * renders twice on every mount and the lint rule `react-hooks/set-state-in-effect`
 * is right to reject it.
 *
 * `getServerSnapshot` returns `light` so the server-rendered markup and the first
 * client render agree. Where the real theme differs, React re-renders after
 * hydration on its own — and because `app/layout.tsx` has already put the right
 * class on `<html>`, and the inline script has already applied the OS
 * preference, that re-render only swaps an icon. No paint is ever wrong.
 */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribeToTheme, getThemeSnapshot, getServerSnapshot);
}

function getThemeSnapshot(): Theme {
  return readThemeFromDocument() ?? "light";
}

function getServerSnapshot(): Theme {
  return "light";
}

/**
 * Observes the class rather than only listening to this tab's own writes, so the
 * toggle also reflects a change made in another tab and re-reads correctly if
 * the class is altered by anything else.
 */
function subscribeToTheme(onStoreChange: () => void): () => void {
  const observer = new MutationObserver(onStoreChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}
