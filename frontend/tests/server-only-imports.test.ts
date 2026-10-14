import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Vitest runs with the frontend directory as its root; there is no reliable
// `__dirname` in this ESM setup.
const ROOT = process.cwd();

/**
 * `lib/api-client.ts` reads cookies from `next/headers`, which only exists in
 * the App Router's server runtime. A client component that *value*-imports
 * anything from a module that imports `api-client` — even transitively — puts
 * `next/headers` into the browser bundle and fails to compile at runtime with
 * a trace that points at an innocent page.
 *
 * The escape hatch is a pure sibling module (`team-category.ts`,
 * `leave-rules-pure.ts`, the `*-client.ts` proxies). Type-only imports are
 * erased and are fine; a value import is not. This test is the guard rail:
 * the mistake is silent in `tsc` and loud in the browser, so it is checked
 * here rather than discovered on a page.
 */

const LIB = join(ROOT, "lib");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      walk(full, out);
    } else if (/\.(ts|tsx)$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

interface ImportRef {
  typeOnly: boolean;
  names: string[];
  spec: string;
}

function importsOf(file: string): ImportRef[] {
  const text = readFileSync(file, "utf8");
  const refs: ImportRef[] = [];
  for (const m of text.matchAll(
    /import\s+(type\s+)?\{([^}]+)\}\s+from\s+["']([^"']+)["']/g
  )) {
    refs.push({
      typeOnly: Boolean(m[1]),
      names: (m[2] || "")
        .split(",")
        .map((n) => n.trim().split(/\s+as\s+/)[0].trim())
        .filter(Boolean),
      spec: m[3],
    });
  }
  for (const m of text.matchAll(
    /import\s+(type\s+)?([A-Za-z0-9_]+)\s+from\s+["']([^"']+)["']/g
  )) {
    refs.push({ typeOnly: Boolean(m[1]), names: [m[2]], spec: m[3] });
  }
  return refs;
}

function resolve(spec: string, fromFile: string): string | null {
  const candidates: string[] = [];
  if (spec.startsWith("@/lib/")) {
    const base = join(LIB, spec.slice("@/lib/".length));
    candidates.push(base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts"));
  } else if (spec.startsWith("@/")) {
    const base = join(ROOT, spec.slice(2));
    candidates.push(base, `${base}.ts`, `${base}.tsx`);
  } else if (spec.startsWith(".")) {
    const base = join(fromFile, "..", spec);
    candidates.push(base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts"));
  }
  for (const c of candidates) {
    try {
      if (statSync(c).isFile()) return c;
    } catch {
      /* not a file; try the next candidate */
    }
  }
  return null;
}

const libFiles = walk(LIB);
// Seed with the modules that are server-only by construction — anything that
// imports `next/headers`, plus anything that imports `api-client` — then grow
// the closure by value-imports.
const serverOnly = new Set(
  libFiles.filter((f) => {
    const text = readFileSync(f, "utf8");
    return (
      /from\s+["']next\/headers["']/.test(text) ||
      /from\s+["'][^"']*api-client["']/.test(text)
    );
  })
);

// Transitive closure: a module is server-only if it value-imports one.
let grew = true;
while (grew) {
  grew = false;
  for (const file of libFiles) {
    if (serverOnly.has(file)) continue;
    for (const ref of importsOf(file)) {
      if (ref.typeOnly) continue;
      const resolved = resolve(ref.spec, file);
      if (resolved && serverOnly.has(resolved)) {
        serverOnly.add(file);
        grew = true;
        break;
      }
    }
  }
}

describe("server-only modules stay out of client bundles", () => {
  it("knows which lib modules read Django through api-client", () => {
    // A canary, so a refactor that stops `teams.ts` importing `api-client`
    // does not quietly disable the rest of this suite.
    expect(serverOnly.has(join(LIB, "api-client.ts"))).toBe(true);
    expect(serverOnly.has(join(LIB, "teams.ts"))).toBe(true);
    expect(serverOnly.has(join(LIB, "leave-rules.ts"))).toBe(true);
  });

  it("finds no client component that value-imports from that closure", () => {
    const offenders: string[] = [];

    for (const dir of ["components", "app"]) {
      for (const file of walk(join(ROOT, dir))) {
        const text = readFileSync(file, "utf8");
        if (!/^\s*["']use client["']/m.test(text)) continue;
        for (const ref of importsOf(file)) {
          if (ref.typeOnly) continue;
          const resolved = resolve(ref.spec, file);
          if (resolved && serverOnly.has(resolved)) {
            offenders.push(
              `${relative(ROOT, file)} -> ${ref.spec} (${ref.names.join(", ")})`
            );
          }
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
