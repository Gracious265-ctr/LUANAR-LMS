import type { NextConfig } from "next";

/**
 * The directives that can be enforced today.
 *
 * Each one is independent: CSP leaves an absent directive unrestricted, so
 * naming only these four cannot change how any resource loads. What they do
 * close is the class of attacks that has nothing to do with loading:
 *
 * - `base-uri 'self'` stops an injected `<base>` from re-pointing every
 *   relative URL on the page (including the links to `/_next/*` bundles) at
 *   another origin.
 * - `object-src 'none'` rules out plugin/embedded-object execution, which no
 *   page here uses.
 * - `frame-ancestors 'none'` is the modern twin of `X-Frame-Options: DENY`.
 * - `form-action 'self'` keeps a compromised page from posting a filled-in
 *   sign-in or password form to an attacker's origin. Every form in this app
 *   submits to a same-origin route handler, so nothing legitimate is affected.
 */
const enforcedCsp = [
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
].join("; ");

/**
 * The full policy, reported but not enforced.
 *
 * `script-src` cannot be enforced yet: Next.js emits inline bootstrap scripts,
 * and blocking them requires a per-request nonce threaded through the proxy.
 * Running the policy in report-only mode collects exactly which inline scripts
 * and inline styles need that treatment, without any risk of a blank page.
 * Violations appear in the browser console (and any `report-uri` added later);
 * the expected report today is the hydration script, and its absence after a
 * nonce rollout is the signal to flip this to `Content-Security-Policy`.
 *
 * `style-src` keeps `'unsafe-inline'` because React renders `style={{...}}`
 * attributes; Tailwind also injects a stylesheet in development. Fonts are
 * self-hosted by `next/font`, so `font-src 'self'` is enough. No page embeds a
 * frame or loads a third-party origin, so `connect-src` and `img-src` stay
 * same-origin (`data:`/`blob:` are allowed because upload previews may use
 * them).
 */
const reportOnlyCsp = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
].join("; ");

/**
 * Response headers that apply to every route.
 *
 * `nosniff` stops a browser from reinterpreting a JSON or upload response as
 * HTML/script; `DENY` keeps the app out of a frame, which also closes click-
 * jacking against the sign-in form; the referrer policy keeps employee ids and
 * application paths out of third-party `Referer` headers; and the permissions
 * policy turns off hardware APIs a leave form never needs. HSTS is deliberately
 * left to the TLS terminator (or Django's production settings), because a
 * header served over plain HTTP in local development is ignored and easy to
 * misread as protection.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  { key: "Content-Security-Policy", value: enforcedCsp },
  { key: "Content-Security-Policy-Report-Only", value: reportOnlyCsp },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
