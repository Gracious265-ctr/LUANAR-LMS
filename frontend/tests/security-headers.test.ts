import { describe, expect, it } from "vitest";

import nextConfig from "@/next.config";

/**
 * The config's `headers()` is the only place these are declared, so reading the
 * returned list is the same thing the Next.js server does at boot. A typo in a
 * directive name would otherwise be silent: CSP ignores a directive it does not
 * recognise, which looks exactly like protection.
 */
async function headerList() {
  const rules = await nextConfig.headers!();
  expect(rules).toHaveLength(1);
  expect(rules[0].source).toBe("/:path*");
  return new Map(rules[0].headers.map(({ key, value }) => [key, value]));
}

describe("security headers", () => {
  it("sends the baseline hardening headers on every route", async () => {
    const headers = await headerList();

    expect(headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(headers.get("X-Frame-Options")).toBe("DENY");
    expect(headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(headers.get("Permissions-Policy")).toContain("camera=()");
  });

  it("enforces only the directives that cannot affect resource loading", async () => {
    const headers = await headerList();
    const csp = headers.get("Content-Security-Policy") ?? "";

    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("form-action 'self'");

    // Enforcing a fetch directive before the nonce work is done would block
    // Next's own scripts. Those stay in the report-only header.
    expect(csp).not.toContain("script-src");
    expect(csp).not.toContain("default-src");
  });

  it("reports the full policy without enforcing it", async () => {
    const headers = await headerList();
    const csp = headers.get("Content-Security-Policy-Report-Only") ?? "";

    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("style-src 'self' 'unsafe-inline'");
    expect(csp).toContain("connect-src 'self'");

    // Report-only must never be mistaken for enforcement.
    expect(csp).not.toContain("frame-ancestors");
  });
});
