import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Vitest runs with the frontend directory as its root.
const ROOT = process.cwd();

/**
 * A module layout renders `ModuleShell` (a client component) and passes it a
 * `navItems` array whose `icon` entries are lucide component references.
 * React Server Components cannot serialize component objects across the
 * server -> client boundary, so the layout itself must be a client component
 * (`"use client"`). When it is not, Next fails at render time with
 * "Only plain objects can be passed to Client Components from Server
 * Components" — a runtime error the build does not catch.
 *
 * This guard walks every `layout.tsx` under `app/`, finds the ones that pass
 * icons to `ModuleShell`, and asserts each declares `use client`. It
 * self-updates as new modules are added.
 */

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      walk(full, out);
    } else if (name === "layout.tsx") {
      out.push(full);
    }
  }
  return out;
}

const isClient = (text: string) => /^\s*["']use client["']/m.test(text);

describe("module layouts that pass icons to a client shell are client components", () => {
  const layouts = walk(join(ROOT, "app"));
  const iconLayouts = layouts.filter((file) => {
    const text = readFileSync(file, "utf8");
    return /ModuleShell/.test(text) && /\bicon:\s*[A-Z]/.test(text);
  });

  it("finds the module layouts (canary so the guard cannot go vacuous)", () => {
    // Four module layouts pass lucide components to `ModuleShell` directly
    // (approvals, documents, hr-admin, leave). The organisation module instead
    // passes icon *names* to its own client layout (`layout-client.tsx`), which
    // maps them to components in the browser, so it carries no serialization
    // hazard and does not match here.
    expect(iconLayouts.length).toBeGreaterThanOrEqual(4);
  });

  it("declares 'use client' in every one of them", () => {
    const offenders = iconLayouts
      .filter((file) => !isClient(readFileSync(file, "utf8")))
      .map((file) => relative(ROOT, file));
    expect(offenders).toEqual([]);
  });
});
