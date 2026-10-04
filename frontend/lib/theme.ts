/**
 * Theme selection for `context/ui-context.md` §13a.
 *
 * The theme is a *preference*, not a secret, so unlike the auth cookies it is
 * deliberately **not** `httpOnly`: a blocking inline script in the document
 * head reads it to pick the right palette before the first paint, and the server
 * reads it to put the same class on `<html>`. Those two readers are why it lives
 * in a cookie rather than in `localStorage` — `localStorage` is invisible to the
 * server, which would force the whole app to render light and correct itself
 * after hydration.
 *
 * This module is imported by client components, so it must not import
 * `next/headers`. The one server-side read lives in `app/layout.tsx`.
 */

export type Theme = "light" | "dark";

export const THEME_COOKIE = "theme";

/** A year. A theme is not something anyone wants to re-pick every few months. */
export const THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

/** The class the whole dark palette hangs off. See `app/globals.css`. */
export const THEME_CLASS = "dark";

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

/** The theme currently on the document, or `null` when the user has no stored choice. */
export function readThemeFromDocument(): Theme | null {
  if (typeof document === "undefined") return null;
  const classes = document.documentElement.classList;
  if (classes.contains(THEME_CLASS)) return "dark";
  if (classes.contains("light")) return "light";
  return null;
}

/** The user's stored choice, independent of what the OS currently reports. */
export function readThemeCookie(): Theme | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === THEME_COOKIE) {
      const value = decodeURIComponent(rest.join("="));
      return isTheme(value) ? value : null;
    }
  }
  return null;
}

/**
 * First visit resolves to the OS preference; an explicit choice always wins and
 * is persisted, so it also wins over the OS on every later visit.
 */
export function resolveInitialTheme(): Theme {
  const stored = readThemeCookie();
  if (stored) return stored;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/** Repaint by class. Both markers are cleared first so they cannot disagree. */
export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const classes = document.documentElement.classList;
  classes.remove("light", THEME_CLASS);
  classes.add(theme);
}

/** Persist and apply in one step, so the two can never diverge. */
export function setTheme(theme: Theme): void {
  if (typeof document !== "undefined") {
    document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=${THEME_COOKIE_MAX_AGE}; samesite=lax`;
  }
  applyTheme(theme);
}

/**
 * The blocking script in `app/layout.tsx`.
 *
 * It runs before the body paints and only ever *adds* a class the server did not
 * already set, so it never fights the server-rendered markup. Keeping it as a
 * string here rather than in the JSX means the two halves of this feature — the
 * class the server picks and the class the browser falls back to — sit in the
 * same file and are read together.
 */
export const THEME_BOOTSTRAP_SCRIPT = `(function(){try{var c=document.documentElement.classList;if(c.contains("${THEME_CLASS}")||c.contains("light"))return;c.add(window.matchMedia("(prefers-color-scheme: dark)").matches?"${THEME_CLASS}":"light");}catch(e){}})();`;
