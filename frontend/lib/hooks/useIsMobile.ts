"use client";

import { useEffect, useState } from "react";

/**
 * The width below which the dashboard collapses its sidebar into a drawer.
 *
 * Kept in sync with the `md` breakpoint in `app/globals.css` (960px). That
 * value is deliberately not imported: the media query lives in CSS and this
 * lives in JS, so the only way to stop them drifting is to name the number
 * once, here, and have the CSS side comment point back at this file.
 */
export const MOBILE_BREAKPOINT_PX = 960;

const QUERY = `(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`;

/**
 * Reports whether the viewport is narrow enough to need the drawer.
 *
 * Returns `false` until the component has mounted, because the server has no
 * viewport to measure. The caller must therefore render the desktop layout for
 * the first paint; rendering the mobile layout on the server and swapping on
 * hydration would flash the wrong shell and re-run every layout effect.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const query = window.matchMedia(QUERY);
    const sync = () => setIsMobile(query.matches);

    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  return isMobile;
}
