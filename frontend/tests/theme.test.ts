import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyTheme,
  readThemeCookie,
  readThemeFromDocument,
  resolveInitialTheme,
  setTheme,
  THEME_BOOTSTRAP_SCRIPT,
  THEME_COOKIE,
} from "@/lib/theme";

/**
 * The bootstrap script is a string that runs before hydration, so jsdom never
 * executes it as part of a render. It is executed here explicitly to pin the one
 * decision it makes, which is the decision that causes a hydration mismatch if it
 * is ever changed carelessly: it may only *fill in* a class the server left
 * unresolved, and must never overwrite one the server resolved from the cookie.
 */
function runBootstrap(matchMediaDark: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({ matches: matchMediaDark })
  );
  // `no-new-func` is not enabled in this project's ESLint config, so no
  // suppression is needed here.
  new Function(THEME_BOOTSTRAP_SCRIPT)();
  vi.unstubAllGlobals();
}

function resetDocument(): void {
  document.documentElement.className = "";
  document.cookie = `${THEME_COOKIE}=; path=/; max-age=0`;
}

afterEach(resetDocument);

describe("theme bootstrap script", () => {
  it("leaves a server-resolved dark class alone", () => {
    document.documentElement.classList.add("dark");

    runBootstrap(false); // system says light, but the stored choice wins

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("light")).toBe(false);
  });

  it("leaves a server-resolved light class alone", () => {
    document.documentElement.classList.add("light");

    runBootstrap(true); // system says dark, but the stored choice wins

    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("resolves the OS preference when the server left the class unresolved", () => {
    runBootstrap(true);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("resolves to light on an unresolved visit when the OS prefers light", () => {
    runBootstrap(false);

    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});

describe("setTheme", () => {
  it("applies the class and persists the choice", () => {
    setTheme("dark");

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(readThemeCookie()).toBe("dark");
  });

  it("switches back and leaves exactly one theme class", () => {
    setTheme("dark");
    setTheme("light");

    const classes = document.documentElement.classList;
    expect(classes.contains("light")).toBe(true);
    expect(classes.contains("dark")).toBe(false);
    expect(readThemeCookie()).toBe("light");
  });
});

describe("applyTheme", () => {
  it("clears both markers before applying, so they cannot disagree", () => {
    document.documentElement.classList.add("dark");

    applyTheme("light");

    expect([...document.documentElement.classList]).toEqual(["light"]);
  });
});

describe("readThemeFromDocument", () => {
  it("reports null when nothing has been resolved yet", () => {
    expect(readThemeFromDocument()).toBeNull();
  });

  it("reports the applied theme", () => {
    applyTheme("dark");
    expect(readThemeFromDocument()).toBe("dark");
  });
});

describe("resolveInitialTheme", () => {
  it("prefers the stored choice over the OS preference", () => {
    document.cookie = `${THEME_COOKIE}=light; path=/`;
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    expect(resolveInitialTheme()).toBe("light");
    vi.unstubAllGlobals();
  });

  it("falls back to the OS preference with no stored choice", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    expect(resolveInitialTheme()).toBe("dark");
    vi.unstubAllGlobals();
  });
});

describe("readThemeCookie", () => {
  it("ignores an unrecognised stored value rather than trusting it", () => {
    document.cookie = `${THEME_COOKIE}=neon; path=/`;

    expect(readThemeCookie()).toBeNull();
  });
});
