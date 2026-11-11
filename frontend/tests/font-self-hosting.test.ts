import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The app's font is self-hosted, and this test is what keeps it that way.
 *
 * `next/font/google` downloads the font files from Google *at build time*. In
 * September 2026 Google started answering some of those downloads with an
 * extensionless `/l/font?kit=…` URL, which Turbopack 16's font replacer cannot
 * parse; the build then dies with the unhelpful "next/font/google queries have
 * exactly one entry" (vercel/next.js#99114). Nothing in the app was wrong — the
 * build depended on a third party's URL format.
 *
 * `next/font/local` reads a committed file instead, so the failure cannot come
 * back and the build stops needing the network. A future change that switches
 * back would look harmless and only fail in CI, so it is asserted here.
 */

const ROOT = join(__dirname, "..");
const SOURCE_DIRS = ["app", "components", "lib"];

function sourceFiles(dir: string): string[] {
  const absolute = join(ROOT, dir);
  if (!existsSync(absolute)) return [];
  return readdirSync(absolute, { withFileTypes: true }).flatMap((entry) => {
    const rel = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(rel);
    return /\.(ts|tsx)$/.test(entry.name) ? [rel] : [];
  });
}

describe("font self-hosting", () => {
  it("never fetches a font over the network at build time", () => {
    const offenders = SOURCE_DIRS.flatMap(sourceFiles).filter((file) =>
      // The comment in layout.tsx explains the reason and therefore names the
      // loader; only an import statement is a real dependency.
      /from\s+["']next\/font\/google["']/.test(
        readFileSync(join(ROOT, file), "utf8")
      )
    );

    expect(offenders).toEqual([]);
  });

  it("ships the committed latin subset that layout.tsx points at", () => {
    const fontPath = join(ROOT, "app", "fonts", "inter-latin.woff2");

    expect(existsSync(fontPath)).toBe(true);
    // A real woff2 starts with the 'wOF2' magic bytes; an HTML error page saved
    // under the right name would otherwise pass a bare existence check.
    const head = readFileSync(fontPath).subarray(0, 4).toString("latin1");
    expect(head).toBe("wOF2");
    expect(statSync(fontPath).size).toBeGreaterThan(1024);
  });

  it("declares the variable weight range the product actually uses", () => {
    const layout = readFileSync(join(ROOT, "app", "layout.tsx"), "utf8");

    // The committed file is Inter's variable latin subset, so one file covers
    // 400-700; the declared range must match what font-normal/medium/semibold/
    // bold ask for, or those weights are silently synthesised by the browser.
    expect(layout).toContain("next/font/local");
    expect(layout).toContain('"./fonts/inter-latin.woff2"');
    expect(layout).toContain('weight: "400 700"');
    expect(layout).toContain('variable: "--font-sans"');
  });
});
